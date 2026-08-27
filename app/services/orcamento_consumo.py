"""Consumo de orçamento do mês e alertas in-app (§4.6).

Cruza o limite mensal (`orcamento_mensal`, materializado sob demanda) com o realizado por
categoria no mês: para despesa, soma de DEBIT; para receita, soma de CREDIT — mesma base do
dashboard (`app.services.dashboard`): exclui transferências (§4.2), corta o período no fuso SP.

Orçamento numa **categoria-pai** cobre o subárvore inteiro (§4.6/#20): o realizado somado é o
das folhas descendentes, não só o lançado diretamente na categoria-pai.

A materialização (`materializar_mes`) só roda como backstop quando o mês pedido é o mês
**corrente** de verdade — meses passados/futuros nunca antes materializados ficam vazios em
vez de ganhar orçamento retroativo baseado no padrão de hoje.

Linhas `suprimido=True` (categoria removida só deste mês, via "Editar mês") continuam nos
`itens` retornados — quem esconde é o consumidor da Visão Geral; "Editar mês" precisa vê-las
pra oferecer "restaurar" em vez de recriar do zero.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.orcamento import Orcamento, OrcamentoMensal
from app.models.transacao import Transacao
from app.schemas.orcamento import OrcamentoConsumoItem, OrcamentoConsumoRead
from app.services.categoria_arvore import subarvores as montar_subarvores
from app.services.orcamento_mensal import materializar_mes
from app.services.periodo import hoje_sp, limites_sp

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


def _valores_por_categoria(
    db: Session, usuario_id: int, ano: int, mes: int
) -> dict[tuple[str, str], int]:
    """{(categoria_efetiva, 'despesa'|'receita'): total_centavos} das transações do mês
    (sem transferência). Sempre em módulo — o sinal de `amount`/`amount_in_account_currency`
    conforme DEBIT/CREDIT não é confiável o bastante pra pautar o sinal exibido (varia entre
    origens), e "gasto"/"recebido" nunca faz sentido negativo pro usuário de qualquer forma."""
    ini, fim_excl = limites_sp(*_intervalo_mes(ano, mes))
    rows = db.execute(
        select(_CAT_EFETIVA, Transacao.type, func.sum(_VALOR_EFETIVO))
        .where(
            Transacao.usuario_id == usuario_id,
            Transacao.date >= ini,
            Transacao.date < fim_excl,
            Transacao.eh_transferencia.is_(False),
            Transacao.type.in_(("DEBIT", "CREDIT")),
        )
        .group_by(_CAT_EFETIVA, Transacao.type)
    ).all()
    valores: dict[tuple[str, str], int] = {}
    for cat, tipo_tx, total in rows:
        if cat is None:
            continue
        valores[(cat, "despesa" if tipo_tx == "DEBIT" else "receita")] = abs(total)
    return valores


def consumo_do_mes(db: Session, usuario_id: int, ano: int, mes: int) -> OrcamentoConsumoRead:
    hoje = hoje_sp()
    if (ano, mes) == (hoje.year, hoje.month):
        materializar_mes(db, usuario_id, ano, mes)  # backstop: só pro mês corrente de verdade
    # Meses passados/futuros: só lê o que já existe — nunca materializa sob demanda.
    mensais = db.scalars(
        select(OrcamentoMensal).where(
            OrcamentoMensal.usuario_id == usuario_id,
            OrcamentoMensal.ano == ano,
            OrcamentoMensal.mes == mes,
        )
    ).all()

    valores = _valores_por_categoria(db, usuario_id, ano, mes)
    subarvores = montar_subarvores(db, usuario_id, {m.categoria_id for m in mensais})
    # (ordem, recorrente) do orçamento padrão — "Editar mês" usa `recorrente` pra saber se
    # remover é "suprimir só este mês" (padrão) ou "apagar de vez" (pontual, ver `criar_pontual`).
    orcamentos_info = {
        oid: (ordem, recorrente)
        for oid, ordem, recorrente in db.execute(
            select(Orcamento.id, Orcamento.ordem, Orcamento.recorrente).where(
                Orcamento.id.in_({m.orcamento_id for m in mensais})
            )
        ).all()
    }

    itens = []
    for m in mensais:
        realizado = sum(valores.get((c, m.tipo), 0) for c in subarvores[m.categoria_id])
        limite = m.limite_centavos
        # Sem limite (0), qualquer realizado já é 100%; sem realizado, 0%.
        percentual = (
            round(realizado / limite * 100) if limite > 0 else (100 if realizado > 0 else 0)
        )
        # Alerta de estouro só existe pra despesa — bater/passar de uma meta de receita é
        # notícia boa, não um alerta.
        alerta = (
            next((lim for lim in _LIMIARES if percentual >= lim), None)
            if m.tipo == "despesa"
            else None
        )
        _, recorrente = orcamentos_info.get(m.orcamento_id, (0, True))
        itens.append(
            OrcamentoConsumoItem(
                orcamento_id=m.orcamento_id,
                orcamento_mensal_id=m.id,
                categoria_id=m.categoria_id,
                tipo=m.tipo,
                recorrente=recorrente,
                suprimido=m.suprimido,
                limite_centavos=limite,
                realizado_centavos=realizado,
                percentual=percentual,
                alerta_atingido=alerta,
            )
        )
    # Ordem definida pelo usuário no modal padrão — não reordena sozinho conforme o gasto muda.
    itens.sort(key=lambda i: (i.tipo, orcamentos_info.get(i.orcamento_id, (0, True))[0]))
    return OrcamentoConsumoRead(ano=ano, mes=mes, itens=itens)
