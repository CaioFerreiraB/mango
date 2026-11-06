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

**Não planejado** (por tipo): o realizado em categorias que nenhuma linha visível do mês cobre
(nem pela subárvore), incluindo transação sem categoria. Pagamento de fatura fica de fora — as
compras do cartão já contam, somar o pagamento seria contar a fatura duas vezes. Categoria
suprimida no mês deixa de estar "no orçamento", então o gasto dela passa a contar aqui.

O drill-down (`transacoes_do_item`) usa exatamente o mesmo recorte (`_filtros_mes` + cobertura),
então a lista de transações de uma linha soma sempre o `realizado_centavos` exibido.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models.categoria import CATEGORIA_PAGAMENTO_FATURA
from app.models.orcamento import Orcamento, OrcamentoMensal
from app.models.transacao import Transacao
from app.schemas.orcamento import OrcamentoConsumoItem, OrcamentoConsumoRead
from app.services.categoria_arvore import com_descendentes
from app.services.categoria_arvore import subarvores as montar_subarvores
from app.services.categoria_resolucao import com_assinatura, expr_categoria_efetiva
from app.services.orcamento_mensal import materializar_mes
from app.services.periodo import hoje_sp, limites_sp

# Do maior para o menor: o primeiro que o percentual cruza é o alerta a exibir.
_LIMIARES = (100, 90, 75, 50)

# Valor efetivo em reais: valor na moeda da conta (internacional), senão o `amount` cru (§4.6).
_VALOR_EFETIVO = func.coalesce(
    Transacao.amount_in_account_currency_centavos, Transacao.amount_centavos
)


def _intervalo_mes(ano: int, mes: int) -> tuple[date, date]:
    inicio = date(ano, mes, 1)
    prox = date(ano + mes // 12, mes % 12 + 1, 1)  # 1º dia do mês seguinte
    return inicio, prox - timedelta(days=1)


_TIPO_TX = {"despesa": "DEBIT", "receita": "CREDIT"}

# ponytail: uma categoria num mês raramente passa de dezenas de linhas; paginar se um dia estourar.
_LIMITE_DRILLDOWN = 500


def _filtros_mes(usuario_id: int, ano: int, mes: int) -> tuple:
    """Recorte do realizado: transações do mês (fuso SP), sem transferência (§4.2)."""
    ini, fim_excl = limites_sp(*_intervalo_mes(ano, mes))
    return (
        Transacao.usuario_id == usuario_id,
        Transacao.date >= ini,
        Transacao.date < fim_excl,
        Transacao.eh_transferencia.is_(False),
    )


def _valores_por_categoria(
    db: Session, usuario_id: int, ano: int, mes: int
) -> dict[tuple[str | None, str], int]:
    """{(categoria_efetiva | None, 'despesa'|'receita'): total_centavos} das transações do mês.

    `abs` por LINHA, não do total: a compra de cartão vem DEBIT com `amount` positivo e o débito
    em conta vem negativo — somar com sinal e tirar o módulo depois fazia os dois se anularem na
    mesma categoria (mesma correção do dashboard). `None` = sem categoria (entra no não planejado).
    """
    cat_efetiva = expr_categoria_efetiva(usuario_id)
    rows = db.execute(
        com_assinatura(
            select(cat_efetiva, Transacao.type, func.sum(func.abs(_VALOR_EFETIVO))), usuario_id
        )
        .where(*_filtros_mes(usuario_id, ano, mes), Transacao.type.in_(tuple(_TIPO_TX.values())))
        .group_by(cat_efetiva, Transacao.type)
    ).all()
    return {
        (cat, "despesa" if tipo_tx == "DEBIT" else "receita"): int(total)
        for cat, tipo_tx, total in rows
    }


def _mensais(db: Session, usuario_id: int, ano: int, mes: int) -> list[OrcamentoMensal]:
    return list(
        db.scalars(
            select(OrcamentoMensal).where(
                OrcamentoMensal.usuario_id == usuario_id,
                OrcamentoMensal.ano == ano,
                OrcamentoMensal.mes == mes,
            )
        ).all()
    )


def _cobertas(
    mensais: list[OrcamentoMensal], subarvores: dict[str, set[str]]
) -> dict[str, set[str]]:
    """Categorias "no orçamento" do mês, por tipo: subárvores das linhas não suprimidas."""
    cobertas: dict[str, set[str]] = {"despesa": set(), "receita": set()}
    for m in mensais:
        if not m.suprimido:
            cobertas[m.tipo] |= subarvores[m.categoria_id]
    return cobertas


def _eh_nao_planejado(cat: str | None, cobertas: set[str]) -> bool:
    return cat is None or (cat not in cobertas and cat != CATEGORIA_PAGAMENTO_FATURA)


def consumo_do_mes(db: Session, usuario_id: int, ano: int, mes: int) -> OrcamentoConsumoRead:
    hoje = hoje_sp()
    if (ano, mes) == (hoje.year, hoje.month):
        materializar_mes(db, usuario_id, ano, mes)  # backstop: só pro mês corrente de verdade
    # Meses passados/futuros: só lê o que já existe — nunca materializa sob demanda.
    mensais = _mensais(db, usuario_id, ano, mes)

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
                notificar=m.notificar,
                limite_centavos=limite,
                realizado_centavos=realizado,
                percentual=percentual,
                alerta_atingido=alerta,
            )
        )
    # Ordem definida pelo usuário no modal padrão — não reordena sozinho conforme o gasto muda.
    itens.sort(key=lambda i: (i.tipo, orcamentos_info.get(i.orcamento_id, (0, True))[0]))
    cobertas = _cobertas(mensais, subarvores)
    nao_planejado = {"despesa": 0, "receita": 0}
    for (cat, tipo), valor in valores.items():
        if _eh_nao_planejado(cat, cobertas[tipo]):
            nao_planejado[tipo] += valor
    return OrcamentoConsumoRead(
        ano=ano,
        mes=mes,
        itens=itens,
        nao_planejado_despesa_centavos=nao_planejado["despesa"],
        nao_planejado_receita_centavos=nao_planejado["receita"],
    )


def transacoes_do_item(
    db: Session, usuario_id: int, ano: int, mes: int, tipo: str, categoria_id: str | None
) -> list[Transacao]:
    """Transações que compõem uma linha do consumo: a subárvore de `categoria_id`, ou — com
    `categoria_id=None` — o não planejado do tipo. Mesmo recorte de `consumo_do_mes`."""
    cat = expr_categoria_efetiva(usuario_id)
    if categoria_id is not None:
        filtro_cat = cat.in_(com_descendentes(db, usuario_id, categoria_id))
    else:
        mensais = _mensais(db, usuario_id, ano, mes)
        subarvores = montar_subarvores(db, usuario_id, {m.categoria_id for m in mensais})
        cobertas = _cobertas(mensais, subarvores)[tipo]
        # Espelha `_eh_nao_planejado` em SQL.
        filtro_cat = or_(
            cat.is_(None), and_(cat.not_in(cobertas), cat != CATEGORIA_PAGAMENTO_FATURA)
        )
    stmt = (
        com_assinatura(select(Transacao), usuario_id)
        .where(*_filtros_mes(usuario_id, ano, mes), Transacao.type == _TIPO_TX[tipo], filtro_cat)
        .order_by(Transacao.date.desc(), Transacao.id.desc())
        .limit(_LIMITE_DRILLDOWN)
    )
    return list(db.scalars(stmt).all())
