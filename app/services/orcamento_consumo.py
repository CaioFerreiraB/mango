"""Consumo de orçamento do mês e alertas in-app (§4.6).

Cruza o limite mensal (`orcamento_mensal`, materializado sob demanda) com o gasto realizado
por categoria no mês. O gasto usa a mesma base do dashboard (`app.services.dashboard`):
exclui transferências (§4.2), soma DEBIT, corta o período no fuso SP.

Orçamento numa **categoria-pai** cobre o subárvore inteiro (§4.6/#20): o gasto somado é o das
folhas descendentes, não só o lançado diretamente na categoria-pai.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.categoria import Categoria
from app.models.orcamento import OrcamentoMensal
from app.models.transacao import Transacao
from app.schemas.orcamento import OrcamentoConsumoItem, OrcamentoConsumoRead
from app.services.orcamento_mensal import materializar_mes
from app.services.periodo import limites_sp

# Do maior para o menor: o primeiro que o percentual cruza é o alerta a exibir.
_LIMIARES = (100, 90, 75, 50)

_CAT_EFETIVA = func.coalesce(Transacao.categoria_override_id, Transacao.categoria_pluggy_id)

# Valor efetivo em reais: valor na moeda da conta (internacional), senão o `amount` cru (§4.6).
_VALOR_EFETIVO = func.coalesce(
    Transacao.amount_in_account_currency_centavos, Transacao.amount_centavos
)


def _intervalo_mes(ano: int, mes: int) -> tuple[date, date]:
    inicio = date(ano, mes, 1)
    prox = date(ano + mes // 12, mes % 12 + 1, 1)  # 1º dia do mês seguinte
    return inicio, prox - timedelta(days=1)


def _gastos_por_categoria(db: Session, usuario_id: int, ano: int, mes: int) -> dict[str, int]:
    """{categoria_efetiva: gasto_centavos} das transações do mês (DEBIT, sem transferência)."""
    ini, fim_excl = limites_sp(*_intervalo_mes(ano, mes))
    rows = db.execute(
        select(_CAT_EFETIVA, func.sum(-_VALOR_EFETIVO))
        .where(
            Transacao.usuario_id == usuario_id,
            Transacao.date >= ini,
            Transacao.date < fim_excl,
            Transacao.eh_transferencia.is_(False),
            Transacao.type == "DEBIT",
        )
        .group_by(_CAT_EFETIVA)
    ).all()
    return {cat: total for cat, total in rows if cat is not None}


def _subarvores(db: Session, raizes: set[str]) -> dict[str, set[str]]:
    """Para cada categoria em `raizes`, o conjunto {ela + descendentes}. Taxonomia é ≤3 níveis
    e pequena → resolvida em memória a partir de `categoria.parent_id`."""
    filhos: dict[str, list[str]] = {}
    for cid, pid in db.execute(select(Categoria.pluggy_id, Categoria.parent_id)).all():
        if pid is not None:
            filhos.setdefault(pid, []).append(cid)

    def descendentes(raiz: str) -> set[str]:
        vistos = {raiz}
        pilha = [raiz]
        while pilha:
            for f in filhos.get(pilha.pop(), []):
                if f not in vistos:
                    vistos.add(f)
                    pilha.append(f)
        return vistos

    return {r: descendentes(r) for r in raizes}


def consumo_do_mes(db: Session, usuario_id: int, ano: int, mes: int) -> OrcamentoConsumoRead:
    materializar_mes(db, usuario_id, ano, mes)  # backstop: garante as linhas do mês
    mensais = db.scalars(
        select(OrcamentoMensal).where(
            OrcamentoMensal.usuario_id == usuario_id,
            OrcamentoMensal.ano == ano,
            OrcamentoMensal.mes == mes,
        )
    ).all()

    gastos = _gastos_por_categoria(db, usuario_id, ano, mes)
    subarvores = _subarvores(db, {m.categoria_id for m in mensais})

    itens = []
    for m in mensais:
        gasto = sum(gastos.get(c, 0) for c in subarvores[m.categoria_id])
        limite = m.limite_centavos
        # Sem limite (0), qualquer gasto já é 100%; sem gasto, 0%.
        percentual = round(gasto / limite * 100) if limite > 0 else (100 if gasto > 0 else 0)
        alerta = next((lim for lim in _LIMIARES if percentual >= lim), None)
        itens.append(
            OrcamentoConsumoItem(
                orcamento_id=m.orcamento_id,
                orcamento_mensal_id=m.id,
                categoria_id=m.categoria_id,
                limite_centavos=limite,
                gasto_centavos=gasto,
                percentual=percentual,
                alerta_atingido=alerta,
            )
        )
    itens.sort(key=lambda i: i.percentual, reverse=True)
    return OrcamentoConsumoRead(ano=ano, mes=mes, itens=itens)
