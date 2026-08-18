"""Leitura agregada da carteira (§4.9): resumo, proventos/DY de FII e série p/ comparação.

Agregação toda server-side (o frontend só exibe). Valores do Pluggy já calculados (#5).
Série histórica: snapshots diários (verdade quando presentes) + reconstrução do passado só
para renda variável com ticker (preço brapi × quantidade). Rentabilidade em TWR diário
encadeado — `r_d = (V_d − F_d − V_{d−1}) / V_{d−1}`, com fluxo F = BUY − SELL do dia, para
aporte não virar ganho.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exceptions import NotFoundError
from app.models.fii_fundamento import FiiFundamento
from app.models.investimento import Investimento, InvestimentoTransacao
from app.models.investimento_saldo_diario import InvestimentoSaldoDiario
from app.models.pluggy import Instituicao, ItemPluggy
from app.models.transacao import Transacao
from app.repositories.ativo import AtivoRepository
from app.repositories.investimento import InvestimentoRepository
from app.repositories.transacao import TransacaoRepository
from app.schemas.investimento import (
    CarteiraAlocacao,
    CarteiraAtivoRF,
    CarteiraAtivoRV,
    CarteiraGrupo,
    CarteiraItem,
    CarteiraPosicao,
    CarteiraResumo,
    CarteiraSerie,
    CarteiraSeriePonto,
    CarteiraTotais,
    CotaSeriePonto,
    FundamentosFII,
    FundamentosFIIAlocacao,
    InvestimentoTransacaoRead,
    ProventosFII,
    VisaoGeralInvestimentos,
)
from app.services import indicadores
from app.services.brapi import token_brapi
from app.services.periodo import SP

logger = logging.getLogger("app.investimento")

RENDA_VARIAVEL = ("EQUITY", "ETF")
RENDA_FIXA = ("FIXED_INCOME",)
_APORTE_RESGATE = ("BUY", "SELL")
# Rendimentos de FII: dividendos pagos pelo fundo, isentos de IR (§4.9). O Pluggy manda `INTEREST`
# em dados reais; `DIVIDEND` aparece no sandbox — ambos são distribuição isenta.
PROVENTO_ISENTO = ("INTEREST", "DIVIDEND")


def _eh_provento(t: InvestimentoTransacao) -> bool:
    """Provento (rendimento) = movimento que não é aplicação/resgate: `INTEREST` explícito ou
    qualquer CREDIT fora de BUY/SELL (ponytail: heurística v1; o sandbox só traz BUY/SELL)."""
    tipo = (t.type or "").upper()
    if tipo in _APORTE_RESGATE:
        return False
    return tipo == "INTEREST" or t.movement_type == "CREDIT"


def _valor(inv: Investimento) -> int:
    """Valor de referência: bruto atual (`amount`), fallback `balance`."""
    return inv.amount_centavos if inv.amount_centavos is not None else inv.saldo_centavos


def _liquido(inv: Investimento) -> int:
    """Valor de resgate: bruto atual menos os impostos que o Pluggy informa (IR + IOF).
    Renda variável não traz impostos (nulos) → líquido = bruto."""
    return _valor(inv) - (inv.taxes_centavos or 0) - (inv.taxes2_centavos or 0)


def _resultado(inv: Investimento) -> int | None:
    if inv.amount_profit_centavos is not None:
        return inv.amount_profit_centavos
    if inv.amount_centavos is not None and inv.amount_original_centavos is not None:
        return inv.amount_centavos - inv.amount_original_centavos
    return None


def _custo_qtd(
    inv: Investimento, analise: dict[int, tuple[int, Decimal]]
) -> tuple[int, Decimal] | None:
    """(custo investido, quantidade correspondente a esse custo) da posição, na ordem de confiança:
    `amountOriginal` do Pluggy (sobre a quantidade atual; qtd 0 em renda fixa, que não usa preço
    médio) → custo reconstruído dos movimentos BUY/SELL, incl. aportes manuais (sobre a quantidade
    reconstruída, < a atual se o histórico é parcial) → None quando não dá p/ determinar."""
    if inv.amount_original_centavos is not None:
        qtd = inv.quantity if inv.quantity is not None else Decimal(0)
        return inv.amount_original_centavos, qtd
    return analise.get(inv.id)


def _investido(inv: Investimento, analise: dict[int, tuple[int, Decimal]]) -> int | None:
    r = _custo_qtd(inv, analise)
    return r[0] if r is not None else None


def _resultado_c(inv: Investimento, analise: dict[int, tuple[int, Decimal]]) -> int | None:
    """Resultado com o mesmo custo de `_investido` — para não sumir quando o Pluggy só manda a
    posição atual sem custo (`amountProfit`/`amountOriginal` nulos). Sobre o custo conhecido: com
    histórico parcial o resultado fica sobre o que se sabe (o aviso de incompleto acompanha)."""
    if inv.amount_profit_centavos is not None:
        return inv.amount_profit_centavos
    investido = _investido(inv, analise)
    if inv.amount_centavos is not None and investido is not None:
        return inv.amount_centavos - investido
    return None


def _custo_reconstruido(
    movimentos: list[InvestimentoTransacao],
) -> tuple[int, Decimal] | None:
    """Custo de aquisição + quantidade da posição atual, reconstruídos dos movimentos BUY/SELL
    pelo método do custo médio. None se faltar quantidade numa compra/venda ou a posição zerar.
    `ponytail:` cobre só BUY/SELL — bonificação/desdobramento/transferência ficam de fora; o
    caller descarta o resultado se a quantidade não bater com a do Pluggy, então movimento não
    coberto vira "—", nunca um preço médio errado."""
    qtd = Decimal(0)
    custo = Decimal(0)
    for m in sorted(movimentos, key=lambda t: (_dia_sp(t.date or t.trade_date) or date.min, t.id)):
        tipo = (m.type or "").upper()
        if tipo == "BUY":
            if m.quantity is None:
                return None
            qtd += m.quantity
            custo += m.amount_centavos
        elif tipo == "SELL":
            if m.quantity is None or qtd <= 0:
                return None
            custo -= custo * m.quantity / qtd  # custo médio: baixa proporcional
            qtd -= m.quantity
    if qtd <= 0:
        return None
    return round(custo), qtd


def _analisar_custos(
    db: Session, invs: list[Investimento]
) -> tuple[dict[int, tuple[int, Decimal]], set[int]]:
    """Para renda variável sem `amountOriginal`, reconstrói o custo dos movimentos BUY/SELL (banco +
    aportes manuais) pelo método do custo médio. Devolve (analise, incompletos):

    - **analise[id] = (custo, qtd_reconstruida)**: sempre que houver algo p/ reconstruir (`qtd>0`),
      mesmo parcial — o cálculo usa o que existe (decisão do usuário).
    - **incompletos**: a qtd reconstruída não cobre a posição atual (>0,5% de diferença) — compras
      fora da janela de 12 meses do banco — ou nem deu p/ reconstruir. Dispara o aviso p/ o usuário
      completar com aportes manuais.

    Uma query batelada para todos os alvos (sem N+1)."""
    alvos = {
        i.id: i for i in invs if i.type in RENDA_VARIAVEL and i.amount_original_centavos is None
    }
    if not alvos:
        return {}, set()
    movs = db.scalars(
        select(InvestimentoTransacao).where(InvestimentoTransacao.investimento_id.in_(list(alvos)))
    ).all()
    por_inv: dict[int, list[InvestimentoTransacao]] = {}
    for m in movs:
        por_inv.setdefault(m.investimento_id, []).append(m)
    analise: dict[int, tuple[int, Decimal]] = {}
    incompletos: set[int] = set()
    for iid, inv in alvos.items():
        r = _custo_reconstruido(por_inv.get(iid, []))
        if r is not None:
            analise[iid] = r  # (custo, qtd) — usado mesmo se parcial
        q = inv.quantity
        if r is None or q is None or q == 0 or abs(r[1] - q) > abs(q) * Decimal("0.005"):
            incompletos.add(iid)  # não cobre a posição atual → pedir aportes manuais
    return analise, incompletos


def _pct(parte: int, base: int | None) -> float | None:
    return round(parte / base * 100, 2) if base else None


def _cotacao_centavos(inv: Investimento) -> int | None:
    """Preço unitário (Pluggy `value_unitario`, em reais) em centavos."""
    return round(float(inv.value_unitario) * 100) if inv.value_unitario is not None else None


def _instituicao_por_item(db: Session, usuario_id: int) -> dict[int, tuple[str | None, str | None]]:
    """item_id → (nome, logo_url) da instituição efetiva: vínculo manual do item (nome+logo,
    sobrepõe o connector), senão o `connector_nome` (sem logo). Espelha o `instituicaoEfetiva`
    das contas para a Carteira."""
    insts = {
        i.id: i
        for i in db.scalars(select(Instituicao).where(Instituicao.usuario_id == usuario_id)).all()
    }
    mapa: dict[int, tuple[str | None, str | None]] = {}
    for item in db.scalars(select(ItemPluggy).where(ItemPluggy.usuario_id == usuario_id)).all():
        inst = insts.get(item.instituicao_manual_id) if item.instituicao_manual_id else None
        mapa[item.id] = (inst.nome, inst.logo_url) if inst else (item.connector_nome, None)
    return mapa


def _instituicao(inv: Investimento, insts: dict[int, tuple[str | None, str | None]]) -> str | None:
    """Instituição efetiva da posição: vínculo manual da conta do item (senão connector);
    fallback emissor. Em dev o connector é sempre "meu Pluggy" — a vinculada é a real."""
    nome, _ = insts.get(inv.item_id, (None, None))
    return nome or inv.instituicao_emissora_nome or inv.issuer


def _logo_instituicao(
    inv: Investimento, insts: dict[int, tuple[str | None, str | None]]
) -> str | None:
    """Logo da instituição efetiva (só há quando vinculada à mão; connector não traz logo)."""
    return insts.get(inv.item_id, (None, None))[1]


def _dia_sp(dt: datetime | None) -> date | None:
    if dt is None:
        return None
    if dt.tzinfo is None:  # SQLite devolve naive; convenção é UTC
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(SP).date()


# --- resumo ---------------------------------------------------------------------------


def resumo_carteira(db: Session, usuario_id: int) -> CarteiraResumo:
    invs = InvestimentoRepository(db, usuario_id).list()
    insts = _instituicao_por_item(db, usuario_id)

    analise, incompletos = _analisar_custos(db, invs)
    total = sum(_valor(i) for i in invs)
    investidos = [v for v in (_investido(i, analise) for i in invs) if v is not None]
    resultados = [r for r in (_resultado_c(i, analise) for i in invs) if r is not None]
    investido = sum(investidos) if investidos else None
    resultado = sum(resultados) if resultados else None
    # Nº de ativos = ativos distintos (como na Carteira): RV por código, RF por ativo do usuário,
    # o resto conta por posição — não o total de aportes/posições.
    rv_keys = {i.code or i.nome or f"#{i.id}" for i in invs if i.type in RENDA_VARIAVEL}
    rf_keys = {
        (i.ativo_id if i.ativo_id is not None else -i.id) for i in invs if i.type in RENDA_FIXA
    }
    outros = sum(1 for i in invs if i.type not in RENDA_VARIAVEL and i.type not in RENDA_FIXA)
    totais = CarteiraTotais(
        valor_centavos=total,
        liquido_centavos=sum(_liquido(i) for i in invs),
        investido_centavos=investido,
        resultado_centavos=resultado,
        resultado_pct=_pct(resultado, investido) if resultado is not None else None,
        quantidade_ativos=len(rv_keys) + len(rf_keys) + outros,
    )

    aloc: dict[str, int] = {}
    for i in invs:
        chave = i.subtype or i.type
        aloc[chave] = aloc.get(chave, 0) + _valor(i)
    alocacao = [
        CarteiraAlocacao(tipo=t, valor_centavos=v, pct=_pct(v, total) or 0.0)
        for t, v in sorted(aloc.items(), key=lambda kv: -kv[1])
    ]

    por_ativo: dict[str, list[Investimento]] = {}
    for i in invs:
        if i.type in RENDA_VARIAVEL:
            por_ativo.setdefault(i.code or i.nome or f"#{i.id}", []).append(i)
    renda_variavel = sorted(
        (_ativo_rv(code, grupo, analise) for code, grupo in por_ativo.items()),
        key=lambda a: -a.valor_centavos,
    )

    # Renda fixa agrupada por ativo do usuário; posição sem ativo (avulsa) vira grupo próprio
    # (chave sintética -id, nunca colide com um ativo_id real).
    nomes_ativo = {a.id: a.nome for a in AtivoRepository(db, usuario_id).list()}
    por_ativo_rf: dict[int, list[Investimento]] = {}
    for i in invs:
        if i.type in RENDA_FIXA:
            por_ativo_rf.setdefault(i.ativo_id if i.ativo_id is not None else -i.id, []).append(i)
    renda_fixa = sorted(
        (_ativo_rf(chave, nomes_ativo, grupo) for chave, grupo in por_ativo_rf.items()),
        key=lambda a: -a.valor_centavos,
    )

    por_tipo: dict[str, list[Investimento]] = {}
    for i in invs:
        por_tipo.setdefault(i.type, []).append(i)
    grupos = sorted(
        (
            CarteiraGrupo(
                type=tipo,
                valor_centavos=sum(_valor(g) for g in itens),
                itens=sorted((_item(g) for g in itens), key=lambda x: -x.valor_centavos),
            )
            for tipo, itens in por_tipo.items()
        ),
        key=lambda g: -g.valor_centavos,
    )

    outros = [i for i in invs if i.type not in RENDA_VARIAVEL and i.type not in RENDA_FIXA]
    posicoes = _posicoes(
        por_ativo, por_ativo_rf, outros, nomes_ativo, insts, total, analise, incompletos
    )

    return CarteiraResumo(
        totais=totais,
        alocacao=alocacao,
        renda_variavel=renda_variavel,
        renda_fixa=renda_fixa,
        grupos=grupos,
        posicoes=posicoes,
    )


def _posicoes(
    por_ativo: dict[str, list[Investimento]],
    por_ativo_rf: dict[int, list[Investimento]],
    outros: list[Investimento],
    nomes_ativo: dict[int, str],
    insts: dict[int, tuple[str | None, str | None]],
    total: int,
    analise: dict[int, tuple[int, Decimal]],
    incompletos: set[int],
) -> list[CarteiraPosicao]:
    """Tabela plana: uma linha por ativo agrupado (mesmas chaves do resumo → mesma contagem)."""
    linhas: list[CarteiraPosicao] = []
    for code, grupo in por_ativo.items():
        rv = _ativo_rv(code, grupo, analise)
        p = grupo[0]
        linhas.append(
            CarteiraPosicao(
                chave=f"rv-{code}",
                nome=rv.nome,
                code=code,
                type=p.type,
                subtype=p.subtype,
                instituicao=_instituicao(p, insts),
                instituicao_logo_url=_logo_instituicao(p, insts),
                quantidade=rv.quantidade,
                preco_medio_centavos=rv.preco_medio_centavos,
                cotacao_centavos=_cotacao_centavos(p),
                investido_centavos=rv.investido_centavos,
                valor_centavos=rv.valor_centavos,
                resultado_centavos=rv.valorizacao_centavos,
                resultado_pct=rv.valorizacao_pct,
                participacao_pct=_pct(rv.valor_centavos, total),
                investimento_ids=rv.investimento_ids,
                historico_incompleto=any(g.id in incompletos for g in grupo),
            )
        )
    for chave, grupo in por_ativo_rf.items():
        rf = _ativo_rf(chave, nomes_ativo, grupo)
        p = grupo[0]
        qtd = sum((g.quantity for g in grupo if g.quantity is not None), Decimal(0))
        tem_qtd = any(g.quantity is not None for g in grupo)
        pm = (
            round(rf.investido_centavos / float(qtd))
            if rf.investido_centavos is not None and tem_qtd and qtd
            else None
        )
        linhas.append(
            CarteiraPosicao(
                chave=f"rf-{rf.ativo_id}" if rf.ativo_id is not None else f"rf-avulsa-{-chave}",
                nome=rf.nome,
                code=p.code,
                type=p.type,
                subtype=p.subtype,
                instituicao=_instituicao(p, insts),
                instituicao_logo_url=_logo_instituicao(p, insts),
                quantidade=float(qtd) if tem_qtd else None,
                preco_medio_centavos=pm,
                cotacao_centavos=_cotacao_centavos(p),
                investido_centavos=rf.investido_centavos,
                valor_centavos=rf.valor_centavos,
                resultado_centavos=rf.resultado_centavos,
                resultado_pct=rf.resultado_pct,
                participacao_pct=_pct(rf.valor_centavos, total),
                investimento_ids=rf.investimento_ids,
            )
        )
    for i in outros:
        valor = _valor(i)
        resultado = _resultado(i)
        linhas.append(
            CarteiraPosicao(
                chave=f"pos-{i.id}",
                nome=i.nome,
                code=i.code,
                type=i.type,
                subtype=i.subtype,
                instituicao=_instituicao(i, insts),
                instituicao_logo_url=_logo_instituicao(i, insts),
                quantidade=float(i.quantity) if i.quantity is not None else None,
                preco_medio_centavos=(
                    round(i.amount_original_centavos / float(i.quantity))
                    if i.amount_original_centavos is not None and i.quantity
                    else None
                ),
                cotacao_centavos=_cotacao_centavos(i),
                investido_centavos=i.amount_original_centavos,
                valor_centavos=valor,
                resultado_centavos=resultado,
                resultado_pct=(
                    _pct(resultado, i.amount_original_centavos) if resultado is not None else None
                ),
                participacao_pct=_pct(valor, total),
                investimento_ids=[i.id],
            )
        )
    linhas.sort(key=lambda linha: -linha.valor_centavos)
    return linhas


def _ativo_rv(
    code: str, grupo: list[Investimento], analise: dict[int, tuple[int, Decimal]]
) -> CarteiraAtivoRV:
    quantidade = sum((g.quantity for g in grupo if g.quantity is not None), Decimal(0))
    tem_quantidade = any(g.quantity is not None for g in grupo)
    # (custo, qtd) por posição: preço médio = Σcusto ÷ Σqtd_base (a qtd a que o custo se refere).
    # Com histórico parcial, qtd_base < quantidade atual → preço médio é a média real do que se
    # conhece, não diluída; investido é só o custo conhecido (decisão do usuário).
    pares = [r for r in (_custo_qtd(g, analise) for g in grupo) if r is not None]
    investido = sum(c for c, _ in pares) if pares else None
    qtd_base = sum((q for _, q in pares), Decimal(0))
    valor = sum(_valor(g) for g in grupo)
    valorizacao = valor - investido if investido is not None else None
    return CarteiraAtivoRV(
        code=code,
        nome=grupo[0].nome,
        investimento_ids=[g.id for g in grupo],
        quantidade=float(quantidade) if tem_quantidade else None,
        preco_medio_centavos=(
            round(investido / float(qtd_base)) if investido is not None and qtd_base else None
        ),
        investido_centavos=investido,
        valor_centavos=valor,
        valorizacao_centavos=valorizacao,
        valorizacao_pct=_pct(valorizacao, investido) if valorizacao is not None else None,
    )


def _ativo_rf(
    chave: int, nomes_ativo: dict[int, str], grupo: list[Investimento]
) -> CarteiraAtivoRF:
    """Renda fixa: resultado do ativo = soma das posições (chave < 0 → posição avulsa sem ativo)."""
    ativo_id = chave if chave >= 0 else None
    investidos = [
        g.amount_original_centavos for g in grupo if g.amount_original_centavos is not None
    ]
    investido = sum(investidos) if investidos else None
    valor = sum(_valor(g) for g in grupo)
    resultados = [r for r in (_resultado(g) for g in grupo) if r is not None]
    resultado = sum(resultados) if resultados else None
    nome = (nomes_ativo.get(ativo_id) if ativo_id is not None else None) or grupo[0].nome
    return CarteiraAtivoRF(
        ativo_id=ativo_id,
        nome=nome,
        investimento_ids=[g.id for g in grupo],
        investido_centavos=investido,
        valor_centavos=valor,
        resultado_centavos=resultado,
        resultado_pct=_pct(resultado, investido) if resultado is not None else None,
        posicoes=sorted((_item(g) for g in grupo), key=lambda x: -x.valor_centavos),
    )


def _item(inv: Investimento) -> CarteiraItem:
    resultado = _resultado(inv)
    return CarteiraItem(
        id=inv.id,
        nome=inv.nome,
        type=inv.type,
        subtype=inv.subtype,
        code=inv.code,
        valor_centavos=_valor(inv),
        investido_centavos=inv.amount_original_centavos,
        resultado_centavos=resultado,
        resultado_pct=(
            _pct(resultado, inv.amount_original_centavos) if resultado is not None else None
        ),
        annual_rate=float(inv.annual_rate) if inv.annual_rate is not None else None,
        last_twelve_months_rate=(
            float(inv.last_twelve_months_rate) if inv.last_twelve_months_rate is not None else None
        ),
        due_date=inv.due_date,
        objetivo_id=inv.objetivo_id,
    )


# --- proventos / DY (§4.9 FII) --------------------------------------------------------


def proventos_fii(
    db: Session, usuario_id: int, investimento_id: int, inicio: date, fim: date
) -> ProventosFII:
    return proventos_posicao(db, usuario_id, [investimento_id], inicio, fim)


def _validar_ids(db: Session, usuario_id: int, ids: list[int]) -> list[Investimento]:
    """Valida posse de cada id (barra IDOR): posição de outro usuário/inexistente → NotFound."""
    repo = InvestimentoRepository(db, usuario_id)
    invs = []
    for i in ids:
        inv = repo.get(i)
        if inv is None:
            raise NotFoundError("investimento não encontrado")
        invs.append(inv)
    return invs


def movimentos_posicao(db: Session, usuario_id: int, ids: list[int]) -> list[InvestimentoTransacao]:
    """Movimentações mescladas de um grupo de posições (compras/vendas/proventos etc.)."""
    _validar_ids(db, usuario_id, ids)
    return db.scalars(
        select(InvestimentoTransacao)
        .where(InvestimentoTransacao.investimento_id.in_(ids))
        .order_by(InvestimentoTransacao.date.desc(), InvestimentoTransacao.id.desc())
    ).all()


# --- aportes manuais (compras que o banco não trouxe, §4.9) ---------------------------


def _valor_unitario(valor_centavos: int, quantidade: Decimal) -> Decimal:
    """Preço unitário em reais (como o `value` do Pluggy) a partir do total em centavos."""
    return (Decimal(valor_centavos) / 100 / quantidade) if quantidade else Decimal(0)


def _get_aporte_manual(db: Session, usuario_id: int, aporte_id: int) -> InvestimentoTransacao:
    """Aporte manual do usuário (barra IDOR e recusa mexer em movimento do Pluggy → 404)."""
    tx = db.scalars(
        select(InvestimentoTransacao)
        .join(Investimento, InvestimentoTransacao.investimento_id == Investimento.id)
        .where(
            InvestimentoTransacao.id == aporte_id,
            InvestimentoTransacao.manual.is_(True),
            Investimento.usuario_id == usuario_id,
        )
    ).first()
    if tx is None:
        raise NotFoundError("aporte manual não encontrado")
    return tx


def criar_aporte_manual(
    db: Session,
    usuario_id: int,
    investimento_id: int,
    data: date,
    quantidade: Decimal,
    valor_centavos: int,
) -> InvestimentoTransacao:
    """Compra informada à mão: vira um BUY manual que entra no custo médio como qualquer outro."""
    _validar_ids(db, usuario_id, [investimento_id])  # posse (S3)
    tx = InvestimentoTransacao(
        investimento_id=investimento_id,
        type="BUY",
        movement_type="CREDIT",
        manual=True,
        amount_centavos=valor_centavos,
        quantity=quantidade,
        value_unitario=_valor_unitario(valor_centavos, quantidade),
        date=datetime(data.year, data.month, data.day, 12, tzinfo=UTC),  # meio-dia UTC evita dia±1
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx


def editar_aporte_manual(
    db: Session, usuario_id: int, aporte_id: int, dados: dict
) -> InvestimentoTransacao:
    tx = _get_aporte_manual(db, usuario_id, aporte_id)
    if "data" in dados:
        d = dados["data"]
        tx.date = datetime(d.year, d.month, d.day, 12, tzinfo=UTC)
    if "quantidade" in dados:
        tx.quantity = dados["quantidade"]
    if "valor_centavos" in dados:
        tx.amount_centavos = dados["valor_centavos"]
    tx.value_unitario = _valor_unitario(tx.amount_centavos, tx.quantity)
    db.commit()
    db.refresh(tx)
    return tx


def excluir_aporte_manual(db: Session, usuario_id: int, aporte_id: int) -> None:
    tx = _get_aporte_manual(db, usuario_id, aporte_id)
    db.delete(tx)
    db.commit()


def proventos_posicao(
    db: Session, usuario_id: int, ids: list[int], inicio: date, fim: date
) -> ProventosFII:
    """Proventos/DY de um grupo de posições (soma; DY = total ÷ valor de referência do grupo)."""
    invs = _validar_ids(db, usuario_id, ids)
    movimentos = db.scalars(
        select(InvestimentoTransacao).where(InvestimentoTransacao.investimento_id.in_(ids))
    ).all()
    com_dia = [
        (dia, t)
        for t in movimentos
        if _eh_provento(t)
        and (dia := _dia_sp(t.date or t.trade_date)) is not None
        and inicio <= dia <= fim
    ]
    com_dia.sort(key=lambda par: par[0], reverse=True)
    proventos = [t for _, t in com_dia]
    total = sum(t.amount_centavos for t in proventos)
    total_isento = sum(
        t.amount_centavos for t in proventos if (t.type or "").upper() in PROVENTO_ISENTO
    )
    valor_ref = sum(_valor(i) for i in invs)
    return ProventosFII(
        investimento_id=ids[0],
        inicio=inicio,
        fim=fim,
        total_centavos=total,
        total_isento_centavos=total_isento,
        dy_pct=_pct(total, valor_ref) if valor_ref > 0 else None,
        proventos=[InvestimentoTransacaoRead.model_validate(t) for t in proventos],
    )


# --- fundamentos de FII (CVM) + evolução da cota (§4.9) -------------------------------

_FII_SUBTYPE = "REAL_ESTATE_FUND"


def _fii_da_posicao(invs: list[Investimento]) -> Investimento | None:
    return next((i for i in invs if (i.subtype or "") == _FII_SUBTYPE), None)


def fundamentos_posicao(db: Session, usuario_id: int, ids: list[int]) -> FundamentosFII:
    """Fundamentos do FII da posição (ponte por ISIN) + P/VP. Não-FII ou sem ingestão →
    `disponivel=False`. Posse dos ids validada (barra IDOR)."""
    invs = _validar_ids(db, usuario_id, ids)
    fii = _fii_da_posicao(invs)
    if fii is None or not fii.isin:
        return FundamentosFII(disponivel=False)
    isin = fii.isin.strip().upper()
    f = db.scalars(select(FiiFundamento).where(FiiFundamento.isin == isin)).first()
    if f is None:
        return FundamentosFII(disponivel=False, isin=isin, cotacao_centavos=_cotacao_centavos(fii))
    cotacao = _cotacao_centavos(fii)
    pvp = (
        round(cotacao / f.valor_patrimonial_cota_centavos, 2)
        if cotacao and f.valor_patrimonial_cota_centavos
        else None
    )
    return FundamentosFII(
        disponivel=True,
        isin=f.isin,
        cnpj=f.cnpj,
        nome=f.nome,
        administrador_nome=f.administrador_nome,
        administrador_cnpj=f.administrador_cnpj,
        data_funcionamento=f.data_funcionamento,
        segmento=f.segmento,
        mandato=f.mandato,
        tipo_gestao=f.tipo_gestao,
        tipo=f.tipo,
        patrimonio_liquido_centavos=f.patrimonio_liquido_centavos,
        num_cotistas=f.num_cotistas,
        valor_patrimonial_cota_centavos=f.valor_patrimonial_cota_centavos,
        dividend_yield_12m_pct=float(f.dividend_yield_12m_pct)
        if f.dividend_yield_12m_pct is not None
        else None,
        vacancia_pct=float(f.vacancia_pct) if f.vacancia_pct is not None else None,
        inadimplencia_pct=float(f.inadimplencia_pct) if f.inadimplencia_pct is not None else None,
        pvp=pvp,
        cotacao_centavos=cotacao,
        data_referencia=f.data_referencia,
        data_referencia_trimestral=f.data_referencia_trimestral,
        atualizado_em=f.atualizado_em,
        alocacao=[
            FundamentosFIIAlocacao(
                classe=a.classe, valor_centavos=a.valor_centavos, pct=float(a.pct)
            )
            for a in sorted(f.alocacao, key=lambda x: -x.valor_centavos)
        ],
    )


def cota_serie_posicao(
    db: Session, usuario_id: int, ids: list[int], inicio: date, fim: date
) -> list[CotaSeriePonto]:
    """Evolução do preço da cota do FII (brapi) no período. Sem ticker/token/preço → lista vazia
    (o gráfico some). Posse validada (barra IDOR)."""
    invs = _validar_ids(db, usuario_id, ids)
    fii = _fii_da_posicao(invs)
    if fii is None or not fii.code:
        return []
    try:
        precos = indicadores.precos_historicos(fii.code, inicio, fim, token_brapi(db, usuario_id))
    except indicadores.IndicadorError as e:
        # brapi grátis limita `range` a 1mo/3mo → HTTP 400 em 6M+; logar p/ não falhar mudo.
        logger.warning("cota-serie de %s indisponível (%s): %s", fii.code, inicio, e)
        return []
    return [
        CotaSeriePonto(data=d, valor_centavos=round(float(v) * 100))
        for d, v in sorted(precos.items())
    ]


# --- sugestão de vínculo transação ↔ provento (§4.9) ----------------------------------

_JANELA_PROVENTO_DIAS = 5


def proventos_sugeridos(
    db: Session, usuario_id: int, transacao_id: int
) -> list[InvestimentoTransacao]:
    """Proventos (do usuário) candidatos a serem o crédito desta transação: mesmo valor e data
    dentro de ±5 dias, ainda não vinculados a outra transação. `ponytail:` valor exato + janela
    fixa; sem tolerância de centavos nem match automático (evita vínculo errado)."""
    tx = TransacaoRepository(db, usuario_id).get(transacao_id)
    if tx is None:
        raise NotFoundError("transação não encontrada")
    alvo = _dia_sp(tx.date)
    if alvo is None:
        return []
    ja_vinculados = select(Transacao.investimento_transacao_id).where(
        Transacao.usuario_id == usuario_id,
        Transacao.investimento_transacao_id.is_not(None),
        Transacao.id != tx.id,
    )
    movimentos = db.scalars(
        select(InvestimentoTransacao)
        .join(Investimento, InvestimentoTransacao.investimento_id == Investimento.id)
        .where(
            Investimento.usuario_id == usuario_id,
            InvestimentoTransacao.amount_centavos == tx.amount_centavos,
            InvestimentoTransacao.id.not_in(ja_vinculados),
        )
    ).all()
    candidatos: list[tuple[int, InvestimentoTransacao]] = []
    for m in movimentos:
        if not _eh_provento(m):
            continue
        dia = _dia_sp(m.date or m.trade_date)
        if dia is None or abs((dia - alvo).days) > _JANELA_PROVENTO_DIAS:
            continue
        candidatos.append((abs((dia - alvo).days), m))
    candidatos.sort(key=lambda par: par[0])
    return [m for _, m in candidatos]


# --- série da carteira (§4.9 comparação) ----------------------------------------------


def serie_carteira(
    db: Session,
    usuario_id: int,
    inicio: date,
    fim: date,
    recorte: str = "todos",
    subtype: str | None = None,
    ids: list[int] | None = None,
    reconstruir_rf: bool = False,
) -> CarteiraSerie:
    invs = InvestimentoRepository(db, usuario_id).list()
    if ids is not None:  # série de uma posição (grupo): só os investimentos do usuário nesse grupo
        alvo = set(ids)
        invs = [i for i in invs if i.id in alvo]
    if subtype is not None:
        invs = [i for i in invs if i.subtype == subtype]
    elif recorte == "renda_fixa":
        invs = [i for i in invs if i.type in RENDA_FIXA]
    elif recorte == "renda_variavel":
        invs = [i for i in invs if i.type in RENDA_VARIAVEL]
    if not invs:
        return CarteiraSerie(recorte=recorte, subtype=subtype, pontos=[])
    ids = [i.id for i in invs]

    snaps = db.execute(
        select(
            InvestimentoSaldoDiario.investimento_id,
            InvestimentoSaldoDiario.data,
            InvestimentoSaldoDiario.valor_centavos,
        ).where(
            InvestimentoSaldoDiario.usuario_id == usuario_id,
            InvestimentoSaldoDiario.investimento_id.in_(ids),
            InvestimentoSaldoDiario.data <= fim,  # sem piso: o último ≤ início semeia o fill
        )
    ).all()
    snap_por_inv: dict[int, dict[date, int]] = {}
    for inv_id, dia, valor in snaps:
        snap_por_inv.setdefault(inv_id, {})[dia] = valor
    primeira_snap = min((min(m) for m in snap_por_inv.values()), default=None)

    movimentos = db.scalars(
        select(InvestimentoTransacao).where(InvestimentoTransacao.investimento_id.in_(ids))
    ).all()
    fluxo_por_dia: dict[date, int] = {}
    for m in movimentos:
        if m.type not in _APORTE_RESGATE:
            continue
        dia = _dia_sp(m.trade_date or m.date)
        if dia is None:
            continue
        sinal = 1 if m.type == "BUY" else -1
        fluxo_por_dia[dia] = fluxo_por_dia.get(dia, 0) + sinal * abs(m.amount_centavos)

    # Passado sem snapshot: renda variável reconstrói pelo preço histórico (brapi). Renda fixa não
    # tem cotação histórica, então só reconstrói quando pedido explicitamente (drawer da posição) e
    # como estimativa — capitaliza os aportes pelo indexador realizado (§ _reconstruir_rf).
    valor_por_dia: dict[date, int] = {}
    reconstruido_ate: date | None = None  # último dia estimado (só renda fixa)
    aplicado_por_dia: dict[date, int] = {}  # capital aplicado reconstruído dia-a-dia (renda fixa)
    so_rv = all(i.type in RENDA_VARIAVEL for i in invs)
    token = token_brapi(db, usuario_id)
    if so_rv and token and (primeira_snap is None or inicio < primeira_snap):
        fim_rec = fim if primeira_snap is None else primeira_snap - timedelta(days=1)
        valor_por_dia = _reconstruir_rv(invs, movimentos, inicio, min(fim, fim_rec), token)
    elif (
        reconstruir_rf
        and all(i.type in RENDA_FIXA for i in invs)
        and (primeira_snap is None or inicio < primeira_snap)
    ):
        # Aportes vêm de purchase_date + amount_original (o Pluggy pode não trazer o BUY p/
        # Tesouro); resgates (SELL) reduzem bruto e aplicado. A reconstrução dá as duas linhas.
        aportes = _aportes_rf(invs)
        resgates: list[tuple[date, int]] = []
        for m in movimentos:
            if m.type != "SELL":
                continue
            d = _dia_sp(m.trade_date or m.date)
            if d is not None:
                resgates.append((d, abs(m.amount_centavos)))
        if aportes:  # fluxo (p/ o TWR não contar aporte/resgate como ganho): +aporte, −resgate
            fluxo_por_dia = {}
            for d, v in aportes:
                fluxo_por_dia[d] = fluxo_por_dia.get(d, 0) + v
            for d, v in resgates:
                fluxo_por_dia[d] = fluxo_por_dia.get(d, 0) - v
        recon = _reconstruir_rf(invs, aportes, resgates, inicio, fim, fim)
        aplicado_por_dia = {d: a for d, (_b, a) in recon.items()}
        fim_rec = fim if primeira_snap is None else primeira_snap - timedelta(days=1)
        for d, (b, _a) in recon.items():
            if d <= fim_rec:  # bruto estimado só antes do 1º snapshot; depois vale a verdade
                valor_por_dia[d] = valor_por_dia.get(d, 0) + b
        reconstruido_ate = max((d for d, _v in recon.items() if d <= fim_rec), default=None)

    # Era dos snapshots: forward-fill por investimento (último snapshot ≤ dia).
    if primeira_snap is not None:
        faixa_ini = max(inicio, primeira_snap)
        for i in invs:
            snaps_inv = snap_por_inv.get(i.id) or {}
            anteriores = [d for d in snaps_inv if d < faixa_ini]
            atual = snaps_inv[max(anteriores)] if anteriores else None
            dia = faixa_ini
            while dia <= fim:
                atual = snaps_inv.get(dia, atual)
                if atual is not None:
                    valor_por_dia[dia] = valor_por_dia.get(dia, 0) + atual
                dia += timedelta(days=1)

    dias = sorted(valor_por_dia)
    if aplicado_por_dia:
        # Renda fixa: linha "aplicado" reconstruída dia-a-dia (aportes − resgates), forward-fill nos
        # dias sem evento (a reconstrução também cobre a era dos snapshots, então é contínua).
        investido_seq: dict[date, int] = {}
        ult = 0
        for dia in dias:
            ult = aplicado_por_dia.get(dia, ult)
            investido_seq[dia] = ult
    else:
        # Demais casos: "aplicado" ancorado no investido atual (amount_original) e recuado pelos
        # fluxos conhecidos — termina certo mesmo sem o BUY inicial. ponytail: aproximação.
        investido_final = sum(
            i.amount_original_centavos for i in invs if i.amount_original_centavos is not None
        )
        fluxo_total = sum(fluxo_por_dia.get(d, 0) for d in dias)
        acc = (investido_final - fluxo_total) if investido_final else 0
        investido_seq = {}
        for dia in dias:
            acc += fluxo_por_dia.get(dia, 0)
            investido_seq[dia] = acc

    pontos: list[CarteiraSeriePonto] = []
    fator = 1.0
    anterior: int | None = None
    for dia in dias:
        valor = valor_por_dia[dia]
        if anterior is not None and anterior > 0:
            fator *= 1 + (valor - fluxo_por_dia.get(dia, 0) - anterior) / anterior
        pontos.append(
            CarteiraSeriePonto(
                data=dia,
                valor_centavos=valor,
                investido_centavos=investido_seq[dia],
                acumulado_pct=round((fator - 1) * 100, 4),
            )
        )
        anterior = valor
    return CarteiraSerie(
        recorte=recorte, subtype=subtype, pontos=pontos, reconstruido_ate=reconstruido_ate
    )


def serie_posicao(
    db: Session, usuario_id: int, ids: list[int], inicio: date, fim: date
) -> CarteiraSerie:
    """Série (evolução da posição) de um grupo, validando posse dos ids (barra IDOR). Reconstrói o
    histórico de renda fixa antes do 1º snapshot (estimativa) para o gráfico ir até a compra."""
    _validar_ids(db, usuario_id, ids)
    return serie_carteira(db, usuario_id, inicio, fim, ids=ids, reconstruir_rf=True)


def _reconstruir_rv(
    invs: list[Investimento],
    movimentos: list[InvestimentoTransacao],
    inicio: date,
    fim: date,
    token: str | None = None,
) -> dict[date, int]:
    """Valor dia-a-dia ≈ fechamento (brapi, forward-fill) × quantidade na data (reconstruída
    p/ trás via BUY/SELL; `ponytail:` sem movimentos com quantidade, assume a atual). Ativo
    sem ticker/preço fica de fora; erro de fonte degrada (série começa no 1º snapshot)."""
    total: dict[date, int] = {}
    for inv in invs:
        if not inv.code or inv.quantity is None:
            continue
        try:
            precos = indicadores.precos_historicos(inv.code, inicio, fim, token)
        except indicadores.IndicadorError:
            continue
        if not precos:
            continue
        movs_inv = [
            m
            for m in movimentos
            if m.investimento_id == inv.id and m.type in _APORTE_RESGATE and m.quantity is not None
        ]
        preco_atual: Decimal | None = None
        dia = inicio
        while dia <= fim:
            preco_atual = precos.get(dia, preco_atual)
            if preco_atual is not None:
                quantidade = _quantidade_em(inv, movs_inv, dia)
                total[dia] = total.get(dia, 0) + int(round(float(preco_atual * quantidade) * 100))
            dia += timedelta(days=1)
    return total


def _quantidade_em(inv: Investimento, movs_inv: list[InvestimentoTransacao], dia: date) -> Decimal:
    quantidade = Decimal(inv.quantity)  # type: ignore[arg-type]  # chamador garante não-nulo
    for m in movimentos_posteriores(movs_inv, dia):
        quantidade += m.quantity if m.type == "SELL" else -m.quantity
    return quantidade if quantidade > 0 else Decimal(0)


def movimentos_posteriores(
    movs: list[InvestimentoTransacao], dia: date
) -> list[InvestimentoTransacao]:
    return [m for m in movs if (d := _dia_sp(m.trade_date or m.date)) is not None and d > dia]


def _indicador_do_titulo(rate_type: str | None) -> str | None:
    """Indicador (BCB) que rege o título p/ reconstrução. Prefixado → None (taxa travada)."""
    t = (rate_type or "").strip().upper()
    if t in ("IPCA", "IGPM", "IGP-M"):
        return "ipca"
    if t == "SELIC":
        return "selic"
    if t in ("CDI", "DI"):
        return "cdi"
    return None


def _aportes_rf(invs: list[Investimento]) -> list[tuple[date, int]]:
    """Aportes de renda fixa a partir de cada lote (data e valor da compra). O Pluggy nem sempre
    traz o BUY como movimento p/ Tesouro, mas dá `purchase_date` + `amount_original` por posição —
    fonte mais confiável do capital aportado e das várias compras do mesmo título."""
    aportes: list[tuple[date, int]] = []
    for i in invs:
        d = _dia_sp(i.purchase_date)
        if d is not None and i.amount_original_centavos is not None:
            aportes.append((d, i.amount_original_centavos))
    return aportes


def _reconstruir_rf(
    invs: list[Investimento],
    aportes: list[tuple[date, int]],
    resgates: list[tuple[date, int]],
    inicio: date,
    fim: date,
    hoje: date,
) -> dict[date, tuple[int, int]]:
    """Reconstrução dia-a-dia (estimativa) da renda fixa: devolve, por dia em [max(inicio, 1ª
    compra), fim], a dupla `(valor bruto, capital aplicado)`, ambos ≥ 0.

    Simula juros compostos dia a dia: o bruto cresce pelo índice realizado do BCB (SELIC/IPCA/CDI;
    prefixado usa a taxa anual travada), cada aporte entra na data da compra e cada resgate (SELL)
    retira a MESMA fração do bruto e do aplicado (`frac = resgate / bruto`, no máx. 1 → nunca fica
    negativo). Um fator único calibra o bruto p/ terminar no valor atual (absorve o cupom real e a
    marcação a mercado). ponytail: rateia o resgate pelo bruto estimado e supõe `amount_original` =
    capital aportado do lote; o aplicado não é calibrado (é o capital, não a marcação)."""
    if not aportes:
        return {}
    base_ini = min(d for d, _ in aportes)
    ini_rec = max(inicio, base_ini)  # não plota antes da 1ª compra
    if ini_rec > fim:
        return {}
    bruto_atual = sum(i.amount_centavos for i in invs if i.amount_centavos is not None)
    if bruto_atual <= 0:
        return {}

    rf = invs[0]
    codigo = _indicador_do_titulo(rf.rate_type)
    annual = float(rf.annual_rate) if rf.annual_rate is not None else 0.0
    acc: dict[date, float] = {}
    if codigo:
        try:
            acc = {d: pct / 100 for d, pct in indicadores.serie(codigo, base_ini, hoje)}
        except indicadores.IndicadorError:
            return {}
        if not acc:
            return {}

    # Fração acumulada do índice por dia (forward-fill), p/ o fator diário = (1+acc_d)/(1+acc_ant).
    acc_ff: dict[date, float] = {}
    corrente = 0.0
    dia = base_ini
    while dia <= hoje:
        corrente = acc.get(dia, corrente)
        acc_ff[dia] = corrente
        dia += timedelta(days=1)
    diario_pre = (1 + annual / 100) ** (1 / 365.25)  # prefixado: fator diário constante

    ap_dia: dict[date, int] = {}
    for d, v in aportes:
        ap_dia[d] = ap_dia.get(d, 0) + v
    rg_dia: dict[date, int] = {}
    for d, v in resgates:
        rg_dia[d] = rg_dia.get(d, 0) + v

    sim: dict[date, tuple[float, float]] = {}
    bruto = 0.0
    aplicado = 0.0
    acc_ant = 0.0
    dia = base_ini
    while dia <= hoje:
        if codigo:
            bruto *= (1 + acc_ff[dia]) / (1 + acc_ant)
            acc_ant = acc_ff[dia]
        elif dia != base_ini:
            bruto *= diario_pre
        aporte = ap_dia.get(dia, 0)
        bruto += aporte
        aplicado += aporte
        resgate = rg_dia.get(dia, 0)
        if resgate > 0 and bruto > 0:
            frac = min(1.0, resgate / bruto)  # não retira mais do que há → nunca negativo
            bruto -= bruto * frac
            aplicado -= aplicado * frac
        sim[dia] = (bruto, aplicado)
        dia += timedelta(days=1)

    bruto_fim = sim[hoje][0] if hoje in sim else 0.0
    k = bruto_atual / bruto_fim if bruto_fim > 0 else 1.0  # calibra o bruto p/ o valor atual
    return {
        d: (max(0, round(k * b)), max(0, round(a)))
        for d, (b, a) in sim.items()
        if ini_rec <= d <= fim
    }


# --- visão geral (dashboard do módulo) ------------------------------------------------


def visao_geral(db: Session, usuario_id: int) -> VisaoGeralInvestimentos:
    """Métricas do dashboard que NÃO vêm do /resumo: rentabilidade 12m (TWR) vs CDI e dividendos
    recebidos no mês corrente (agregação da carteira inteira)."""
    hoje = datetime.now(SP).date()

    # Rentabilidade 12m (TWR) + comparação com o CDI no mesmo período (janela realmente disponível).
    inicio_12m = hoje - timedelta(days=365)
    serie = serie_carteira(db, usuario_id, inicio_12m, hoje)
    rent_12m = serie.pontos[-1].acumulado_pct if serie.pontos else None
    vs_cdi: float | None = None
    if rent_12m is not None:
        try:
            cdi = indicadores.serie("cdi", inicio_12m, hoje)
        except indicadores.IndicadorError:
            cdi = []
        if cdi:
            vs_cdi = round(rent_12m - cdi[-1][1], 2)

    # Dividendos recebidos no mês corrente (carteira inteira; por-investimento é proventos_fii).
    movimentos = db.scalars(
        select(InvestimentoTransacao)
        .join(Investimento, InvestimentoTransacao.investimento_id == Investimento.id)
        .where(Investimento.usuario_id == usuario_id)
    ).all()
    dividendos_mes = 0
    for m in movimentos:
        if not _eh_provento(m):
            continue
        dia = _dia_sp(m.date or m.trade_date)
        if dia is not None and dia.year == hoje.year and dia.month == hoje.month:
            dividendos_mes += m.amount_centavos

    return VisaoGeralInvestimentos(
        rentabilidade_12m_pct=rent_12m,
        vs_cdi_pp=vs_cdi,
        dividendos_mes_centavos=dividendos_mes,
    )
