"""Agregações do dashboard (§4.10). Tudo escopado por `usuario_id` (S3) e no fuso SP.

Regra central: entradas/saídas **excluem** `eh_transferencia=true` — é o que impede a dupla
contagem entre o gasto no cartão (competência) e o pagamento da fatura (caixa) (§4.2).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.cartao_fatura import Fatura
from app.models.conta import Conta
from app.models.transacao import Transacao
from app.schemas.dashboard import (
    DashboardResumo,
    DashboardSeries,
    FaturaResumoBucket,
    FaturasResumo,
    GastoCategoria,
    SerieBucket,
)
from app.services.categoria_resolucao import com_assinatura, expr_categoria_efetiva
from app.services.gasto_usuario import VALOR_EFETIVO, linhas_do_periodo
from app.services.periodo import SP, limites_sp
from app.services.revisao import expr_pendente_revisao

_TOP_CATEGORIAS = 8
_ULTIMAS = 10
_FATURAS_ABERTAS = 5
_FATURAS_GRAFICO = 6

# Categoria efetiva: a precedência mora em `categoria_resolucao` (fonte única, §4.5) e depende
# do usuário (assinatura + categorias desativadas), então é montada por query, não em módulo.


def _totais(linhas) -> tuple[int, int, dict[str | None, int]]:
    """(entradas, saídas, gasto por categoria) das linhas de `gasto_usuario.linhas_do_periodo`
    — já na parte do usuário (divisão) e em grandeza; quem diz entrada/saída é o `type`."""
    entradas = saidas = 0
    por_cat: dict[str | None, int] = {}
    for _, valor, tipo, cat in linhas:
        if tipo == "CREDIT":
            entradas += valor
        else:
            saidas += valor
            por_cat[cat] = por_cat.get(cat, 0) + valor
    return entradas, saidas, por_cat


def _saldo_em_contas(db: Session, usuario_id: int) -> int:
    """Saldo somado das contas BANK (cartão não tem saldo, tem fatura)."""
    return db.scalar(
        select(func.coalesce(func.sum(Conta.saldo_centavos), 0)).where(
            Conta.usuario_id == usuario_id, Conta.type == "BANK"
        )
    )


def _contar_pendentes(db: Session, do_usuario, corte: datetime | None) -> int:
    """Transações na fila de revisão (§4.3).

    Contagem GLOBAL de propósito (não respeita o período do dashboard): a fila é uma pendência do
    usuário, não um recorte temporal. O corte tira o histórico que ele já declarou que não vai
    revisar.
    """
    return db.scalar(
        select(func.count()).select_from(Transacao).where(do_usuario, expr_pendente_revisao(corte))
    )


def _gasto_por_categoria(por_cat: dict[str | None, int]) -> list[GastoCategoria]:
    """Top-N categorias por gasto no período, pela categoria efetiva (§4.5)."""
    top = sorted(por_cat.items(), key=lambda kv: kv[1], reverse=True)[:_TOP_CATEGORIAS]
    return [GastoCategoria(categoria_id=cat, total_centavos=total) for cat, total in top]


def _ultimas_transacoes(db: Session, do_usuario) -> list[Transacao]:
    """As mais recentes do usuário, sem recorte de período (é um atalho, não um relatório)."""
    return list(
        db.scalars(
            select(Transacao)
            .where(do_usuario)
            .order_by(Transacao.date.desc(), Transacao.id.desc())
            .limit(_ULTIMAS)
        ).all()
    )


def _faturas_abertas(db: Session, usuario_id: int) -> list[Fatura]:
    """Próximas faturas a vencer."""
    return list(
        db.scalars(
            select(Fatura)
            .where(Fatura.usuario_id == usuario_id, Fatura.due_date >= datetime.now(UTC))
            .order_by(Fatura.due_date.asc())
            .limit(_FATURAS_ABERTAS)
        ).all()
    )


def montar_dashboard(
    db: Session,
    usuario_id: int,
    inicio: date,
    fim: date,
    corte_revisao: datetime | None = None,
) -> DashboardResumo:
    ini, fim_excl = limites_sp(inicio, fim)
    do_usuario = Transacao.usuario_id == usuario_id
    entradas, saidas, por_cat = _totais(linhas_do_periodo(db, usuario_id, ini, fim_excl))

    return DashboardResumo(
        saldo_total_centavos=_saldo_em_contas(db, usuario_id),
        entradas_centavos=entradas,
        saidas_centavos=saidas,
        resultado_centavos=entradas - saidas,
        nao_revisadas=_contar_pendentes(db, do_usuario, corte_revisao),
        gasto_por_categoria=_gasto_por_categoria(por_cat),
        ultimas_transacoes=_ultimas_transacoes(db, do_usuario),
        faturas_abertas=_faturas_abertas(db, usuario_id),
    )


# Segmento sintético que fecha a quebra por categoria no total da fatura: o `totalAmount` do Pluggy
# inclui encargos (IOF/juros/multa), saldo anterior e estornos — que não são compras categorizáveis.
# O frontend rotula esse id (ver grafico-faturas.tsx).
AJUSTE_CATEGORIA_ID = "__ajuste__"


def _fechar_no_total(cats: list[GastoCategoria], total: int) -> list[GastoCategoria]:
    """Anexa o ajuste = total − compras, para os segmentos somarem o total da fatura na vírgula."""
    ajuste = total - sum(g.total_centavos for g in cats)
    if ajuste != 0:
        cats = [*cats, GastoCategoria(categoria_id=AJUSTE_CATEGORIA_ID, total_centavos=ajuste)]
    return cats


def resumo_faturas(
    db: Session, usuario_id: int, cartao_id: int, limite: int = _FATURAS_GRAFICO
) -> FaturasResumo:
    """Últimas `limite` faturas do cartão em ordem cronológica (esquerda→direita no gráfico): o
    valor total é o da própria fatura; a quebra por categoria soma as compras (`bill_id`) que caem
    nela + um segmento "encargos e ajustes" que fecha exatamente no total (§4.2)."""
    faturas = list(
        db.scalars(
            select(Fatura)
            .where(Fatura.usuario_id == usuario_id, Fatura.cartao_id == cartao_id)
            .order_by(Fatura.due_date.desc())
            .limit(limite)
        ).all()
    )
    faturas.reverse()  # mais antiga → mais recente
    if not faturas:
        return FaturasResumo(buckets=[])

    ids = [f.id for f in faturas]
    # Grandeza do gasto = |valor| das compras (DEBIT). `abs` porque o cartão traz `amount` com sinal
    # invertido em relação à conta bancária (compra positiva) — sem isso a barra fica negativa e o
    # top-N por categoria escolhe as menores. Estornos (CREDIT) já ficam de fora pelo filtro
    # de tipo.
    cat_efetiva = expr_categoria_efetiva(usuario_id)
    linhas = db.execute(
        com_assinatura(
            select(Transacao.bill_id, cat_efetiva, func.sum(func.abs(VALOR_EFETIVO))), usuario_id
        )
        .where(
            Transacao.usuario_id == usuario_id,
            Transacao.bill_id.in_(ids),
            Transacao.type == "DEBIT",
            Transacao.eh_transferencia.is_(False),
        )
        .group_by(Transacao.bill_id, cat_efetiva)
    ).all()

    por_fatura: dict[int, list[GastoCategoria]] = {}
    for bill_id, cat, total in linhas:
        por_fatura.setdefault(bill_id, []).append(
            GastoCategoria(categoria_id=cat, total_centavos=total)
        )

    return FaturasResumo(
        buckets=[
            FaturaResumoBucket(
                fatura_id=f.id,
                due_date=f.due_date.date(),
                total_centavos=f.total_amount_centavos,
                por_categoria=_fechar_no_total(
                    sorted(
                        por_fatura.get(f.id, []),
                        key=lambda g: g.total_centavos,
                        reverse=True,
                    ),
                    f.total_amount_centavos,
                ),
            )
            for f in faturas
        ]
    )


def _inicio_bucket(d: date, granularidade: str) -> date:
    """Início do período que contém `d`: o próprio dia (diária), 1º dia do mês (mensal) ou
    segunda-feira (semanal)."""
    if granularidade == "diaria":
        return d
    if granularidade == "mensal":
        return d.replace(day=1)
    return d - timedelta(days=d.weekday())


def _proximo_bucket(inicio: date, granularidade: str) -> date:
    if granularidade == "diaria":
        return inicio + timedelta(days=1)
    if granularidade == "mensal":
        return (inicio.replace(day=28) + timedelta(days=4)).replace(day=1)
    return inicio + timedelta(days=7)


def montar_series(
    db: Session, usuario_id: int, inicio: date, fim: date, granularidade: str = "semanal"
) -> DashboardSeries:
    """Série temporal de entradas/saídas/resultado e gasto por categoria, agrupada por semana ou
    mês no fuso SP. Mesmas regras dos KPIs (exclui transferências, sinal DEBIT/CREDIT, categoria
    efetiva) para os totais reconciliarem. Bucketização em Python — resultado idêntico nos dois
    bancos, sem `date_trunc`/`strftime`."""
    ini, fim_excl = limites_sp(inicio, fim)
    linhas = linhas_do_periodo(db, usuario_id, ini, fim_excl)

    # Buckets vazios de inicio→fim para os gráficos não pularem períodos sem transação.
    buckets: dict[date, dict] = {}
    b = _inicio_bucket(inicio, granularidade)
    while b <= fim:
        buckets[b] = {"entradas": 0, "saidas": 0, "cat": {}}
        b = _proximo_bucket(b, granularidade)

    for dt, valor, tipo, cat in linhas:
        chave = _inicio_bucket(dt.astimezone(SP).date(), granularidade)
        bal = buckets.setdefault(chave, {"entradas": 0, "saidas": 0, "cat": {}})
        # Grandeza já resolvida (e na parte do usuário) por `linhas_do_periodo`.
        if tipo == "CREDIT":
            bal["entradas"] += valor
        else:
            bal["saidas"] += valor
            bal["cat"][cat] = bal["cat"].get(cat, 0) + valor

    return DashboardSeries(
        buckets=[
            SerieBucket(
                inicio=chave,
                entradas_centavos=bal["entradas"],
                saidas_centavos=bal["saidas"],
                resultado_centavos=bal["entradas"] - bal["saidas"],
                por_categoria=[
                    GastoCategoria(categoria_id=c, total_centavos=t)
                    for c, t in sorted(bal["cat"].items(), key=lambda kv: kv[1], reverse=True)
                ],
            )
            for chave, bal in sorted(buckets.items())
        ]
    )
