"""Agregações do dashboard (§4.10). Tudo escopado por `usuario_id` (S3) e no fuso SP.

Regra central: entradas/saídas **excluem** `eh_transferencia=true` — é o que impede a dupla
contagem entre o gasto no cartão (competência) e o pagamento da fatura (caixa) (§4.2).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from fractions import Fraction

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.cartao_fatura import Cartao, Fatura
from app.models.conta import Conta
from app.models.investimento import Investimento
from app.models.investimento_saldo_diario import InvestimentoSaldoDiario
from app.models.orcamento import OrcamentoMensal
from app.models.transacao import Transacao
from app.schemas.dashboard import (
    AcumuladoPonto,
    AnaliseNatureza,
    CartaoPainel,
    CartoesResumo,
    ContaTotal,
    ContraparteTotal,
    DashboardResumo,
    DashboardSeries,
    DiaSemanaTotal,
    FaturaResumoBucket,
    FaturasResumo,
    GastoCategoria,
    MeioTotal,
    PatrimonioPonto,
    PatrimonioSerie,
    PrevistoMes,
    SerieBucket,
)
from app.services import saldo_diario
from app.services.categoria_arvore import subarvores as montar_subarvores
from app.services.categoria_resolucao import com_assinatura, expr_categoria_efetiva
from app.services.gasto_usuario import (
    VALOR_EFETIVO,
    Lancamento,
    categorias_investimento,
    lancamentos_do_periodo,
    linhas_do_periodo,
    tipo_do_lancamento,
)
from app.services.orcamento_mensal import materializar_mes
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
    """Início do período que contém `d`: o próprio dia (diária), 1º dia do mês (mensal), 1º de
    janeiro (anual) ou segunda-feira (semanal)."""
    if granularidade == "diaria":
        return d
    if granularidade == "anual":
        return d.replace(month=1, day=1)
    if granularidade == "mensal":
        return d.replace(day=1)
    return d - timedelta(days=d.weekday())


def _proximo_bucket(inicio: date, granularidade: str) -> date:
    if granularidade == "diaria":
        return inicio + timedelta(days=1)
    if granularidade == "anual":
        return inicio.replace(year=inicio.year + 1)
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


def _saldo_bank_por_dia(db: Session, usuario_id: int, hoje: date, inicio: date) -> dict[date, int]:
    saldo_dia: dict[date, int] = {}
    for serie in saldo_diario.series(db, usuario_id, (hoje - inicio).days + 1):
        for p in serie.pontos:
            saldo_dia[p.data] = saldo_dia.get(p.data, 0) + p.saldo_centavos
    return saldo_dia


def _razao_liquida(db: Session, usuario_id: int) -> dict[int, tuple[int, int]]:
    """{investimento: (líquido, bruto) atuais}: razão em inteiros (sem float em dinheiro)."""
    razao: dict[int, tuple[int, int]] = {}
    for inv in db.scalars(select(Investimento).where(Investimento.usuario_id == usuario_id)):
        bruto = inv.amount_centavos if inv.amount_centavos is not None else inv.saldo_centavos
        razao[inv.id] = (bruto - (inv.taxes_centavos or 0) - (inv.taxes2_centavos or 0), bruto)
    return razao


def _estimar_liquido(valor: int, razao: tuple[int, int]) -> int:
    """valor × líquido/bruto arredondado (meio para cima), em inteiros; bruto 0 → razão 1."""
    liq, bruto = razao
    if not bruto:
        return valor
    return (2 * valor * liq + bruto) // (2 * bruto)


def _snapshots(db: Session, usuario_id: int, hoje: date) -> dict[int, list[tuple]]:
    """{investimento: [(data, bruto, líquido|None)]} em ordem de data, até hoje."""
    snaps: dict[int, list[tuple]] = {}
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
    return snaps


def _carteira_no_fecho(
    snaps: dict[int, list[tuple]], razao: dict[int, tuple[int, int]], fim: date
) -> tuple[int, int, bool, bool]:
    """(bruto, líquido, estimado, tem) no fecho: último snapshot de cada investimento."""
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
            liquido += _estimar_liquido(ultimo[1], razao.get(inv_id, (1, 1)))
        else:
            liquido += ultimo[2]
    return bruto, liquido, estimado, tem


def montar_patrimonio(db: Session, usuario_id: int, meses: int = 12) -> PatrimonioSerie:
    """Evolução patrimonial mês a mês: contas BANK (reconstrução de `saldo_diario`) + carteira
    (último snapshot de cada investimento até o fecho do mês). Líquido = bruto − IR − IOF; snapshot
    antigo sem `liquido_centavos` usa a razão líquido/bruto atual do investimento (estimativa)."""
    hoje = hoje_sp()
    fechos = _fechos_mensais(hoje, meses)
    saldo_dia = _saldo_bank_por_dia(db, usuario_id, hoje, fechos[0][1].replace(day=1))
    razao = _razao_liquida(db, usuario_id)
    snaps = _snapshots(db, usuario_id, hoje)
    pontos: list[PatrimonioPonto] = []
    for mes, fim in fechos:
        bruto, liquido, estimado, tem = _carteira_no_fecho(snaps, razao, fim)
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


def _compras_por_cartao(
    db: Session, usuario_id: int, ids: list[int], hoje: date
) -> tuple[dict[int, int], dict[int, int], dict[int, int]]:
    """(mês, ano até hoje, futuras) das compras por cartão: DEBIT sem transferência, em grandeza
    por linha (`abs`: compra de cartão vem DEBIT com amount positivo do Pluggy)."""
    ini_mes, _ = limites_sp(hoje.replace(day=1), hoje)
    ini_ano, fim_hoje = limites_sp(hoje.replace(month=1, day=1), hoje)
    mes: dict[int, int] = {}
    ano: dict[int, int] = {}
    futuras: dict[int, int] = {}
    for conta_id, dt, valor in db.execute(
        select(Transacao.conta_id, Transacao.date, func.abs(VALOR_EFETIVO)).where(
            Transacao.usuario_id == usuario_id,
            Transacao.conta_id.in_(ids),
            Transacao.type == "DEBIT",
            Transacao.eh_transferencia.is_(False),
            Transacao.date >= ini_ano,
        )
    ):
        dt = dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)
        if dt >= fim_hoje:
            futuras[conta_id] = futuras.get(conta_id, 0) + valor
            continue
        ano[conta_id] = ano.get(conta_id, 0) + valor
        if dt >= ini_mes:
            mes[conta_id] = mes.get(conta_id, 0) + valor
    return mes, ano, futuras


def _proximos_vencimentos(db: Session, usuario_id: int, hoje: date) -> dict[int, date]:
    """Vencimento sem `balance_due_date`: a próxima fatura conhecida a partir de hoje (SP)."""
    ini_hoje, _ = limites_sp(hoje, hoje)
    prox: dict[int, date] = {}
    for cartao_id, due in db.execute(
        select(Fatura.cartao_id, func.min(Fatura.due_date))
        .where(Fatura.usuario_id == usuario_id, Fatura.due_date >= ini_hoje)
        .group_by(Fatura.cartao_id)
    ):
        due = due if due.tzinfo is not None else due.replace(tzinfo=UTC)
        prox[cartao_id] = due.astimezone(SP).date()
    return prox


def montar_cartoes(db: Session, usuario_id: int) -> CartoesResumo:
    """Painel dos cartões: por cartão, compras do mês, fatura atual, próximas (data futura), limite
    e disponível; e o resumo global (inclui total do ano e média mensal). Datas no fuso SP."""
    hoje = hoje_sp()
    contas = db.execute(
        select(Conta, Cartao)
        .outerjoin(Cartao, Cartao.conta_id == Conta.id)
        .where(Conta.usuario_id == usuario_id, Conta.type == "CREDIT")
        .order_by(Conta.id)
    ).all()
    mes, ano, futuras = _compras_por_cartao(db, usuario_id, [c.id for c, _ in contas], hoje)
    prox_venc = _proximos_vencimentos(db, usuario_id, hoje)
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


# --- Abas Receitas / Despesas ------------------------------------------------------------------

_TOP_CONTRAPARTES = 5
SEM_CONTRAPARTE = "Não identificado"


def _menos_meses(d: date, meses: int) -> date:
    total = d.year * 12 + d.month - 1 - meses
    ano, mes = divmod(total, 12)
    ultimo = (date(ano + (mes + 1) // 12, (mes + 1) % 12 + 1, 1) - timedelta(days=1)).day
    return date(ano, mes + 1, min(d.day, ultimo))


def periodo_anterior(inicio: date, fim: date) -> tuple[date, date]:
    """Período anterior equivalente: começando no dia 1º, os mesmos dias N meses antes (1–23/nov →
    1–23/out); senão, os N dias imediatamente antes."""
    if inicio.day == 1:
        meses = (fim.year - inicio.year) * 12 + fim.month - inicio.month + 1
        return _menos_meses(inicio, meses), _menos_meses(fim, meses)
    n = (fim - inicio).days + 1
    return inicio - timedelta(days=n), inicio - timedelta(days=1)


def chave_contraparte(nome: str | None) -> str:
    return " ".join((nome or "").split()).casefold()


def _meses_entre(inicio: date, fim: date) -> list[tuple[int, int]]:
    out, (a, m) = [], (inicio.year, inicio.month)
    while (a, m) <= (fim.year, fim.month):
        out.append((a, m))
        a, m = (a + 1, 1) if m == 12 else (a, m + 1)
    return out


def _orcado_por_mes(
    db: Session, usuario_id: int, tipo: str, meses: list[tuple[int, int]]
) -> dict[tuple[int, int], int]:
    """Soma dos limites do tipo por mês, só das linhas-raiz (orçamento de subcategoria já está
    dentro do da categoria-pai, regra #20). Mês sem linha visível fica de fora. O mês corrente é
    materializado como em `orcamento_consumo` (backstop); passados/futuros só leem o que existe."""
    hoje = hoje_sp()
    if (hoje.year, hoje.month) in meses:
        materializar_mes(db, usuario_id, hoje.year, hoje.month)
    linhas = db.execute(
        select(
            OrcamentoMensal.ano,
            OrcamentoMensal.mes,
            OrcamentoMensal.categoria_id,
            OrcamentoMensal.limite_centavos,
        ).where(
            OrcamentoMensal.usuario_id == usuario_id,
            OrcamentoMensal.tipo == tipo,
            OrcamentoMensal.suprimido.is_(False),
            OrcamentoMensal.ano * 100 + OrcamentoMensal.mes >= meses[0][0] * 100 + meses[0][1],
            OrcamentoMensal.ano * 100 + OrcamentoMensal.mes <= meses[-1][0] * 100 + meses[-1][1],
        )
    ).all()
    arv = montar_subarvores(db, usuario_id, {c for _, _, c, _ in linhas})
    por_mes: dict[tuple[int, int], list[tuple[str, int]]] = {}
    for a, m, c, lim in linhas:
        por_mes.setdefault((a, m), []).append((c, lim))
    out: dict[tuple[int, int], int] = {}
    for chave, itens in por_mes.items():
        cats = [c for c, _ in itens]
        out[chave] = sum(lim for c, lim in itens if not any(o != c and c in arv[o] for o in cats))
    return out


def _da_natureza(
    lancs: list[Lancamento], natureza: str, investimento: set[str]
) -> list[Lancamento]:
    return [x for x in lancs if tipo_do_lancamento(x.categoria, x.tipo, investimento) == natureza]


def _nome_contas(db: Session, usuario_id: int) -> dict[int, str]:
    return {
        cid: mn or nome or "Conta"
        for cid, mn, nome in db.execute(
            select(Conta.id, Conta.marketing_name, Conta.nome).where(Conta.usuario_id == usuario_id)
        )
    }


def _ranking_contrapartes(
    atual: list[Lancamento],
) -> tuple[list[ContraparteTotal], list[ContraparteTotal]]:
    """(top 5, resto) das contrapartes com total > 0, agrupadas pelo nome normalizado."""
    contrap: dict[str, list] = {}  # chave → [nome, total, quantidade]
    for x in atual:
        c = contrap.setdefault(
            chave_contraparte(x.contraparte), [x.contraparte or SEM_CONTRAPARTE, 0, 0]
        )
        c[1] += x.valor
        c[2] += 1
    ranking = sorted(
        (
            ContraparteTotal(chave=k, nome=n, total_centavos=t, quantidade=q)
            for k, (n, t, q) in contrap.items()
            if t > 0
        ),
        key=lambda c: c.total_centavos,
        reverse=True,
    )
    return ranking[:_TOP_CONTRAPARTES], ranking[_TOP_CONTRAPARTES:]


def _meios(atual: list[Lancamento], nomes: dict[int, str]) -> list[MeioTotal]:
    """Total por meio de pagamento, com a quebra por conta/cartão (maior primeiro)."""
    meios: dict[str, dict[int | None, int]] = {}
    for x in atual:
        m = meios.setdefault(x.meio, {})
        m[x.conta_id] = m.get(x.conta_id, 0) + x.valor
    por_meio = (
        MeioTotal(
            meio=meio,
            total_centavos=sum(por_conta.values()),
            por_conta=sorted(
                (
                    ContaTotal(conta_id=cid, nome=nomes.get(cid, "Conta"), total_centavos=v)
                    for cid, v in por_conta.items()
                    if cid is not None and v > 0
                ),
                key=lambda c: c.total_centavos,
                reverse=True,
            ),
        )
        for meio, por_conta in meios.items()
    )
    return sorted(por_meio, key=lambda m: m.total_centavos, reverse=True)


def _dias_semana(pares: list[tuple[Lancamento, date]], inicio: date, ate: date):
    """Total e ocorrências de cada dia da semana em [inicio, ate] — dias sem gasto contam."""
    ocorr = [0] * 7
    d = inicio
    while d <= ate:
        ocorr[d.weekday()] += 1
        d += timedelta(days=1)
    tot = [0] * 7
    for x, dd in pares:
        if inicio <= dd <= ate:
            tot[dd.weekday()] += x.valor
    return [DiaSemanaTotal(dia=i, total_centavos=tot[i], ocorrencias=ocorr[i]) for i in range(7)]


def _dias_no_mes(d: date) -> int:
    return (_menos_meses(d.replace(day=1), -1) - timedelta(days=1)).day


def _acumulado(
    por_dia: dict[date, int],
    atual: tuple[date, date],
    anterior: tuple[date, date],
    orcado: dict[tuple[int, int], int],
    hoje: date,
) -> list[AcumuladoPonto]:
    """Acumulado dia a dia (atual × anterior, alinhados pelo índice do dia) + ritmo do orçamento
    (limite do mês pró-rata por dia; `Fraction` para não usar float em dinheiro)."""
    (inicio, fim), (ant_ini, ant_fim) = atual, anterior
    n_ant = (ant_fim - ant_ini).days + 1
    pontos: list[AcumuladoPonto] = []
    soma_at = soma_ant = 0
    esperado = Fraction(0)
    for i in range((fim - inicio).days + 1):
        d = inicio + timedelta(days=i)
        soma_at += por_dia.get(d, 0)
        if i < n_ant:
            soma_ant += por_dia.get(ant_ini + timedelta(days=i), 0)
        lim = orcado.get((d.year, d.month))
        if lim is not None:
            esperado += Fraction(lim, _dias_no_mes(d))
        pontos.append(
            AcumuladoPonto(
                indice=i,
                data=d,
                atual_centavos=soma_at if d <= hoje else None,
                anterior_centavos=soma_ant if i < n_ant else None,
                esperado_centavos=round(esperado) if orcado else None,
            )
        )
    return pontos


def _previsto(
    pares: list[tuple[Lancamento, date]],
    meses: list[tuple[int, int]],
    orcado: dict[tuple[int, int], int],
) -> list[PrevistoMes]:
    """Orçado × realizado de cada mês inteiro que o período toca."""
    realizado: dict[tuple[int, int], int] = {}
    for x, dd in pares:
        chave = (dd.year, dd.month)
        if chave in meses:
            realizado[chave] = realizado.get(chave, 0) + x.valor
    return [
        PrevistoMes(
            mes=f"{a:04d}-{m:02d}",
            previsto_centavos=orcado.get((a, m)),
            realizado_centavos=realizado.get((a, m), 0),
        )
        for a, m in meses
    ]


def montar_analise(
    db: Session, usuario_id: int, natureza: str, inicio: date, fim: date
) -> AnaliseNatureza:
    """Tudo das abas Receitas/Despesas numa leitura só da base de `gasto_usuario` (mesma regra dos
    KPIs e do orçamento): totais vs período anterior, categorias, top contrapartes, meios de
    pagamento, média por dia da semana, acumulado diário e previsto (orçamento) × realizado."""
    hoje = hoje_sp()
    ant_ini, ant_fim = periodo_anterior(inicio, fim)
    meses = _meses_entre(inicio, fim)
    mes_fim = _menos_meses(date(*meses[-1], 1), -1) - timedelta(days=1)
    ini_dt, fim_excl = limites_sp(min(ant_ini, date(*meses[0], 1)), max(fim, mes_fim))
    lancs = _da_natureza(
        lancamentos_do_periodo(db, usuario_id, ini_dt, fim_excl),
        natureza,
        categorias_investimento(db, usuario_id),
    )
    pares = [(x, x.data.astimezone(SP).date()) for x in lancs]
    atual = [x for x, d in pares if inicio <= d <= fim]
    anterior = [x for x, d in pares if ant_ini <= d <= ant_fim]
    por_cat: dict[str | None, int] = {}
    por_dia: dict[date, int] = {}
    for x, d in pares:
        por_dia[d] = por_dia.get(d, 0) + x.valor
    for x in atual:
        por_cat[x.categoria] = por_cat.get(x.categoria, 0) + x.valor
    top, resto = _ranking_contrapartes(atual)
    orcado = _orcado_por_mes(db, usuario_id, natureza, meses)
    return AnaliseNatureza(
        natureza=natureza,
        anterior_inicio=ant_ini,
        anterior_fim=ant_fim,
        total_centavos=sum(x.valor for x in atual),
        anterior_centavos=sum(x.valor for x in anterior),
        quantidade=len(atual),
        por_categoria=_gasto_por_categoria(por_cat),
        contrapartes=top,
        outras_contrapartes_centavos=sum(c.total_centavos for c in resto),
        outras_contrapartes_quantidade=len(resto),
        meios=_meios(atual, _nome_contas(db, usuario_id)),
        # Só até hoje: dia futuro não "aconteceu".
        dias_semana=_dias_semana(pares, inicio, min(fim, hoje)),
        acumulado=_acumulado(por_dia, (inicio, fim), (ant_ini, ant_fim), orcado, hoje),
        previsto=_previsto(pares, meses, orcado),
    )


@dataclass(frozen=True)
class FiltroLancamentos:
    """Pedaço da análise aberto no drill-down (os campos combinam por AND; None = qualquer)."""

    categoria_id: str | None = None
    contraparte: str | None = None  # chave normalizada (`chave_contraparte`)
    meio: str | None = None
    conta_id: int | None = None

    def aceita(self, x: Lancamento) -> bool:
        return (
            (self.categoria_id is None or x.categoria == self.categoria_id)
            and (self.contraparte is None or chave_contraparte(x.contraparte) == self.contraparte)
            and (self.meio is None or x.meio == self.meio)
            and (self.conta_id is None or x.conta_id == self.conta_id)
        )


def lancamentos_da_analise(
    db: Session,
    usuario_id: int,
    natureza: str,
    periodo: tuple[date, date],
    filtro: FiltroLancamentos,
) -> list[Lancamento]:
    """Drill-down de um pedaço da análise — o mesmo recorte de `montar_analise`, então a lista
    soma exatamente o valor do gráfico. Mais recentes primeiro."""
    ini, fim_excl = limites_sp(*periodo)
    lancs = _da_natureza(
        lancamentos_do_periodo(db, usuario_id, ini, fim_excl),
        natureza,
        categorias_investimento(db, usuario_id),
    )
    return sorted((x for x in lancs if filtro.aceita(x)), key=lambda x: x.data, reverse=True)
