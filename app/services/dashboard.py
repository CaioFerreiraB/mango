"""Agregações do dashboard (§4.10). Tudo escopado por `usuario_id` (S3) e no fuso SP.

Regra central: entradas/saídas **excluem** `eh_transferencia=true` — é o que impede a dupla
contagem entre o gasto no cartão (competência) e o pagamento da fatura (caixa) (§4.2).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.cartao_fatura import Cartao, Fatura
from app.models.conta import Conta
from app.models.investimento import Investimento
from app.models.investimento_saldo_diario import InvestimentoSaldoDiario
from app.models.transacao import Transacao
from app.schemas.dashboard import (
    CartaoPainel,
    CartoesResumo,
    DashboardResumo,
    DashboardSeries,
    FaturaResumoBucket,
    FaturasResumo,
    GastoCategoria,
    PatrimonioPonto,
    PatrimonioSerie,
    SerieBucket,
)
from app.services import saldo_diario
from app.services.categoria_resolucao import com_assinatura, expr_categoria_efetiva
from app.services.gasto_usuario import (
    VALOR_EFETIVO,
    categorias_investimento,
    linhas_do_periodo,
    tipo_do_lancamento,
)
from app.services.periodo import SP, hoje_sp, limites_sp
from app.services.revisao import expr_pendente_revisao

_ULTIMAS = 10
_FATURAS_ABERTAS = 5
_FATURAS_GRAFICO = 6

# Categoria efetiva: a precedência mora em `categoria_resolucao` (fonte única, §4.5) e depende
# do usuário (assinatura + categorias desativadas), então é montada por query, não em módulo.


def _totais(linhas, investimento: set[str]) -> tuple[int, int, int, dict[str | None, int]]:
    """(entradas, saídas, investido, gasto por categoria) das linhas de
    `gasto_usuario.linhas_do_periodo` — já na parte do usuário (divisão) e em grandeza; quem diz
    entrada/saída é o `type`. Categoria de investimento não é entrada/saída: aporte (DEBIT) −
    resgate (CREDIT) vai para `investido`, que pode ficar negativo."""
    entradas = saidas = investido = 0
    por_cat: dict[str | None, int] = {}
    for _, valor, tipo_tx, cat in linhas:
        tipo = tipo_do_lancamento(cat, tipo_tx, investimento)
        if tipo == "investimento":
            investido += valor if tipo_tx == "DEBIT" else -valor
        elif tipo == "receita":
            entradas += valor
        else:
            saidas += valor
            por_cat[cat] = por_cat.get(cat, 0) + valor
    return entradas, saidas, investido, por_cat


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
    """Todas as categorias com gasto no período, maior primeiro, pela categoria efetiva (§4.5)."""
    top = sorted(por_cat.items(), key=lambda kv: kv[1], reverse=True)
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
    entradas, saidas, investido, por_cat = _totais(
        linhas_do_periodo(db, usuario_id, ini, fim_excl), categorias_investimento(db, usuario_id)
    )

    return DashboardResumo(
        saldo_total_centavos=_saldo_em_contas(db, usuario_id),
        entradas_centavos=entradas,
        saidas_centavos=saidas,
        resultado_centavos=entradas - saidas,
        investido_centavos=investido,
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
    por_bucket: dict[date, list] = {}
    b = _inicio_bucket(inicio, granularidade)
    while b <= fim:
        por_bucket[b] = []
        b = _proximo_bucket(b, granularidade)
    for linha in linhas:
        chave = _inicio_bucket(linha[0].astimezone(SP).date(), granularidade)
        por_bucket.setdefault(chave, []).append(linha)
    investimento = categorias_investimento(db, usuario_id)
    # Mesma regra dos KPIs (`_totais`): os buckets somam o resumo do mesmo período.
    totais = {chave: _totais(ls, investimento) for chave, ls in por_bucket.items()}

    return DashboardSeries(
        buckets=[
            SerieBucket(
                inicio=chave,
                entradas_centavos=ent,
                saidas_centavos=sai,
                resultado_centavos=ent - sai,
                investido_centavos=inv,
                por_categoria=_gasto_por_categoria(cat),
            )
            for chave, (ent, sai, inv, cat) in sorted(totais.items())
        ]
    )


def _fechos_mensais(hoje: date, meses: int) -> list[tuple[str, date]]:
    """[(YYYY-MM, último dia do mês)] dos `meses` meses até o corrente, que fecha `hoje`."""
    fechos: list[tuple[str, date]] = []
    inicio_mes = hoje.replace(day=1)
    fim = hoje
    for _ in range(meses):
        fechos.append((inicio_mes.strftime("%Y-%m"), fim))
        fim = inicio_mes - timedelta(days=1)
        inicio_mes = fim.replace(day=1)
    fechos.reverse()
    return fechos


def montar_patrimonio(db: Session, usuario_id: int, meses: int = 12) -> PatrimonioSerie:
    """Evolução patrimonial mês a mês: contas BANK (reconstrução de `saldo_diario`) + carteira
    (último snapshot de cada investimento até o fecho do mês). Líquido = bruto − IR − IOF; snapshot
    antigo sem `liquido_centavos` usa a razão líquido/bruto atual do investimento (estimativa)."""
    hoje = hoje_sp()
    fechos = _fechos_mensais(hoje, meses)
    inicio = fechos[0][1].replace(day=1)

    saldo_dia: dict[date, int] = {}
    for serie in saldo_diario.series(db, usuario_id, (hoje - inicio).days + 1):
        for p in serie.pontos:
            saldo_dia[p.data] = saldo_dia.get(p.data, 0) + p.saldo_centavos

    invs = db.scalars(select(Investimento).where(Investimento.usuario_id == usuario_id)).all()
    razao: dict[int, float] = {}
    for inv in invs:
        bruto = inv.amount_centavos if inv.amount_centavos is not None else inv.saldo_centavos
        liq = bruto - (inv.taxes_centavos or 0) - (inv.taxes2_centavos or 0)
        razao[inv.id] = liq / bruto if bruto else 1.0
    snaps: dict[int, list[tuple[date, int, int | None]]] = {}
    for inv_id, dia, valor, liquido in db.execute(
        select(
            InvestimentoSaldoDiario.investimento_id,
            InvestimentoSaldoDiario.data,
            InvestimentoSaldoDiario.valor_centavos,
            InvestimentoSaldoDiario.liquido_centavos,
        )
        .where(
            InvestimentoSaldoDiario.usuario_id == usuario_id, InvestimentoSaldoDiario.data <= hoje
        )
        .order_by(InvestimentoSaldoDiario.data)
    ):
        snaps.setdefault(inv_id, []).append((dia, valor, liquido))

    pontos: list[PatrimonioPonto] = []
    for mes, fim in fechos:
        bruto = liquido = 0
        estimado = tem = False
        for inv_id, lista in snaps.items():
            # ponytail: varredura linear por mês (dezenas de investimentos × ~365 snapshots).
            ultimo = next((s for s in reversed(lista) if s[0] <= fim), None)
            if ultimo is None:
                continue
            tem = True
            bruto += ultimo[1]
            if ultimo[2] is None:
                estimado = True
                liquido += round(ultimo[1] * razao.get(inv_id, 1.0))
            else:
                liquido += ultimo[2]
        contas = saldo_dia.get(fim, 0)
        pontos.append(
            PatrimonioPonto(
                mes=mes,
                contas_centavos=contas,
                investimentos_centavos=bruto,
                investimentos_liquido_centavos=liquido,
                total_centavos=contas + bruto,
                liquido_centavos=contas + liquido,
                liquido_estimado=estimado,
                tem_investimentos=tem,
            )
        )
    return PatrimonioSerie(pontos=pontos)


def montar_cartoes(db: Session, usuario_id: int) -> CartoesResumo:
    """Painel dos cartões: por cartão, compras do mês, fatura atual, próximas (data futura), limite
    e disponível; e o resumo global (inclui total do ano e média mensal). Datas no fuso SP."""
    hoje = hoje_sp()
    ini_mes, _ = limites_sp(hoje.replace(day=1), hoje)
    ini_ano, fim_hoje = limites_sp(hoje.replace(month=1, day=1), hoje)

    contas = db.execute(
        select(Conta, Cartao)
        .outerjoin(Cartao, Cartao.conta_id == Conta.id)
        .where(Conta.usuario_id == usuario_id, Conta.type == "CREDIT")
        .order_by(Conta.id)
    ).all()
    if not contas:
        return CartoesResumo(
            compras_mes_centavos=0,
            fatura_atual_centavos=0,
            proximas_centavos=0,
            total_ano_centavos=0,
            media_mes_centavos=0,
            cartoes=[],
        )
    ids = [c.id for c, _ in contas]

    # Compras (DEBIT, sem transferência) do ano até hoje e futuras, por cartão; grandeza por linha
    # (`abs`: compra de cartão vem DEBIT com amount positivo do Pluggy).
    linhas = db.execute(
        select(Transacao.conta_id, Transacao.date, func.abs(VALOR_EFETIVO)).where(
            Transacao.usuario_id == usuario_id,
            Transacao.conta_id.in_(ids),
            Transacao.type == "DEBIT",
            Transacao.eh_transferencia.is_(False),
            Transacao.date >= ini_ano,
        )
    ).all()
    mes: dict[int, int] = {}
    ano: dict[int, int] = {}
    futuras: dict[int, int] = {}
    for conta_id, dt, valor in linhas:
        dt = dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)
        if dt >= fim_hoje:
            futuras[conta_id] = futuras.get(conta_id, 0) + valor
            continue
        ano[conta_id] = ano.get(conta_id, 0) + valor
        if dt >= ini_mes:
            mes[conta_id] = mes.get(conta_id, 0) + valor

    # Vencimento sem `balance_due_date`: a próxima fatura conhecida.
    prox_venc: dict[int, date] = {}
    for cartao_id, due in db.execute(
        select(Fatura.cartao_id, func.min(Fatura.due_date))
        .where(Fatura.usuario_id == usuario_id, Fatura.due_date >= ini_mes)
        .group_by(Fatura.cartao_id)
    ):
        due = due if due.tzinfo is not None else due.replace(tzinfo=UTC)
        prox_venc[cartao_id] = due.astimezone(SP).date()

    cartoes = [
        CartaoPainel(
            conta_id=conta.id,
            nome=conta.marketing_name or conta.nome or "Cartão",
            fecha=cartao.balance_close_date if cartao else None,
            vence=(cartao.balance_due_date if cartao else None) or prox_venc.get(conta.id),
            limite_centavos=cartao.credit_limit_centavos if cartao else None,
            disponivel_centavos=cartao.available_credit_limit_centavos if cartao else None,
            compras_mes_centavos=mes.get(conta.id, 0),
            fatura_atual_centavos=abs(conta.saldo_centavos),
            proximas_centavos=futuras.get(conta.id, 0),
        )
        for conta, cartao in contas
    ]
    total_ano = sum(ano.values())
    return CartoesResumo(
        compras_mes_centavos=sum(c.compras_mes_centavos for c in cartoes),
        fatura_atual_centavos=sum(c.fatura_atual_centavos for c in cartoes),
        proximas_centavos=sum(c.proximas_centavos for c in cartoes),
        total_ano_centavos=total_ano,
        media_mes_centavos=round(total_ano / hoje.month),
        cartoes=cartoes,
    )
