"""Quanto de cada lançamento é do usuário — base única de orçamento e dashboard.

- Transação vinculada a uma divisão (`divisao_despesa.transacao_id`) conta só a parcela do
  usuário (`divisao_participante.valor_centavos`; sem linha = 0, ex.: modo `integral` em que o
  outro deve tudo). As demais contam o valor efetivo inteiro, em módulo (o sinal do `amount` não
  é confiável por tipo — quem diz entrada/saída é o `type`).
- Parcelas de divisão sem transação do usuário — pagas por outra pessoa, ou pagas por ele "fora
  do banco" (`sem_transacao`) — entram como DEBIT na data/categoria da divisão. Categoria
  personalizada de outro usuário não é dele → `None` (sem categoria).
- Divisão paga pelo usuário e ainda sem vínculo é pendência: não soma nada extra (a transação
  bancária, se existir, ainda conta cheia até ser vinculada).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import NamedTuple

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.models.categoria import Categoria
from app.models.conta import Conta
from app.models.divisao import DivisaoDespesa, DivisaoParticipante
from app.models.transacao import Transacao, TransacaoPagamento
from app.services.categoria_arvore import subarvores as montar_subarvores
from app.services.categoria_resolucao import com_assinatura, expr_categoria_efetiva

# Valor efetivo em reais = valor na moeda da conta (compra internacional), senão o `amount` cru.
VALOR_EFETIVO = func.coalesce(
    Transacao.amount_in_account_currency_centavos, Transacao.amount_centavos
)

_DivTx = aliased(DivisaoDespesa, name="divisao_tx")
_PartTx = aliased(DivisaoParticipante, name="participante_tx")

# Exige `com_divisao` na query.
VALOR_USUARIO = case(
    (_DivTx.id.is_not(None), func.coalesce(_PartTx.valor_centavos, 0)),
    else_=func.abs(VALOR_EFETIVO),
)


def com_divisao(stmt):
    """Outerjoins que `VALOR_USUARIO` referencia. Ambos são no máximo 1 linha por transação
    (`transacao_id` é único; participante é único por divisão+usuário) — não duplica soma."""
    return stmt.outerjoin(_DivTx, _DivTx.transacao_id == Transacao.id).outerjoin(
        _PartTx,
        and_(_PartTx.divisao_id == _DivTx.id, _PartTx.usuario_id == Transacao.usuario_id),
    )


def categoria_da_divisao(usuario_id: int):
    """Categoria da divisão vista pelo usuário (exige outerjoin em `Categoria`)."""
    return case(
        (
            or_(Categoria.usuario_id.is_(None), Categoria.usuario_id == usuario_id),
            DivisaoDespesa.categoria_id,
        )
    )


def parcelas_divisao(usuario_id: int):
    """SELECT (divisao_id, categoria_id, data, valor) das parcelas do usuário que viram lançamento
    próprio. O chamador acrescenta o recorte de data em `DivisaoDespesa.data`."""
    return (
        select(
            DivisaoDespesa.id.label("divisao_id"),
            categoria_da_divisao(usuario_id).label("categoria_id"),
            DivisaoDespesa.data.label("data"),
            DivisaoParticipante.valor_centavos.label("valor"),
            DivisaoDespesa.descricao.label("descricao"),
        )
        .join(
            DivisaoParticipante,
            and_(
                DivisaoParticipante.divisao_id == DivisaoDespesa.id,
                DivisaoParticipante.usuario_id == usuario_id,
            ),
        )
        .outerjoin(Categoria, Categoria.pluggy_id == DivisaoDespesa.categoria_id)
        .where(
            DivisaoDespesa.arquivada.is_(False),
            DivisaoParticipante.valor_centavos > 0,
            or_(
                DivisaoDespesa.pago_por_usuario_id != usuario_id,
                DivisaoDespesa.sem_transacao.is_(True),
            ),
        )
    )


# Investimento = subárvore 03 menos os rendimentos (0306 juros/dividendos), que são receita.
# Fonte única de orçamento e dashboard: aporte/resgate não é despesa/receita.
RAIZ_INVESTIMENTO = "03000000"
RAIZ_RENDIMENTOS = "03060000"


def categorias_investimento(db: Session, usuario_id: int) -> set[str]:
    """Categorias de investimento do usuário (pela árvore: pega personalizadas filhas)."""
    arv = montar_subarvores(db, usuario_id, {RAIZ_INVESTIMENTO, RAIZ_RENDIMENTOS})
    return arv[RAIZ_INVESTIMENTO] - arv[RAIZ_RENDIMENTOS]


def tipo_do_lancamento(cat: str | None, tipo_tx: str, investimento: set[str]) -> str:
    """'investimento' | 'despesa' | 'receita' de uma linha de `linhas_do_periodo`."""
    if cat in investimento:
        return "investimento"
    return "despesa" if tipo_tx == "DEBIT" else "receita"


RAIZ_RENDA = "01000000"


def categorias_renda(db: Session, usuario_id: int) -> set[str]:
    """Subárvore "Renda" (salário, aposentadoria, renda não-recorrente…, com personalizadas)."""
    return montar_subarvores(db, usuario_id, {RAIZ_RENDA})[RAIZ_RENDA]


def expr_estorno_cartao(usuario_id: int, cat, renda: set[str]):
    """Crédito numa conta de cartão fora da Renda = estorno/crédito de compra: abate a despesa da
    categoria em vez de virar receita. Crédito categorizado como Renda (ex.: cashback como renda)
    segue receita. Pagamento de fatura não chega aqui (é transferência, §4.2)."""
    cartoes = select(Conta.id).where(Conta.usuario_id == usuario_id, Conta.type == "CREDIT")
    return and_(
        Transacao.type == "CREDIT",
        Transacao.conta_id.in_(cartoes),
        or_(cat.is_(None), cat.not_in(renda)),
    )


# Meio de pagamento pelo que o banco informa (Open Finance `operationType`, senão o método do
# `paymentData`). Cartão de crédito vem do tipo da conta. Desconhecido → "Outros".
_MEIO = {
    "PIX": "Pix",
    "TED": "Transferência",
    "DOC": "Transferência",
    "TRANSFERENCIA_MESMA_INSTITUICAO": "Transferência",
    "BOLETO": "Boleto",
    "CONVENIO_ARRECADACAO": "Boleto",
    "CARTAO": "Cartão de débito",
    "SAQUE": "Saque",
    "DEPOSITO": "Depósito",
    "FOLHA_PAGAMENTO": "Folha de pagamento",
    "TARIFA_SERVICOS_AVULSOS": "Tarifas bancárias",
    "PACOTE_TARIFA_SERVICOS": "Tarifas bancárias",
    "ENCARGOS_JUROS_CHEQUE_ESPECIAL": "Encargos",
}
MEIO_CARTAO_CREDITO = "Cartão de crédito"
MEIO_DIVISAO = "Divisão"


def meio_de(conta_tipo: str | None, operacao: str | None, metodo: str | None) -> str:
    if conta_tipo == "CREDIT":
        return MEIO_CARTAO_CREDITO
    return _MEIO.get(operacao or "") or _MEIO.get(metodo or "") or "Outros"


class Lancamento(NamedTuple):
    """Um lançamento do usuário no período, já na parte dele (divisão) e em grandeza.
    `tipo` diz receita/despesa; estorno de cartão vem como DEBIT com `valor` negativo."""

    data: datetime  # aware
    valor: int
    tipo: str  # DEBIT | CREDIT
    categoria: str | None
    transacao_id: int | None
    divisao_id: int | None
    conta_id: int | None
    contraparte: str | None  # quem recebeu (despesa) / quem pagou (receita), como o banco nomeia
    meio: str


def _select_transacoes(usuario_id: int, renda: set[str]):
    """SELECT das transações não-transferência com tudo que `Lancamento` precisa (colunas
    rotuladas). O chamador acrescenta o recorte de data."""
    cat = expr_categoria_efetiva(usuario_id)
    estorno = expr_estorno_cartao(usuario_id, cat, renda)
    stmt = select(
        Transacao.date.label("data"),
        VALOR_USUARIO.label("valor"),
        Transacao.type.label("tipo"),
        cat.label("categoria"),
        Transacao.id.label("transacao_id"),
        Transacao.conta_id,
        case((estorno, True), else_=False).label("estorno"),
        Conta.type.label("conta_tipo"),
        Transacao.operation_type,
        TransacaoPagamento.metodo,
        Transacao.descricao_usuario,
        Transacao.merchant_nome,
        TransacaoPagamento.receiver_nome,
        TransacaoPagamento.payer_nome,
        Transacao.description,
    )
    return (
        com_divisao(com_assinatura(stmt, usuario_id))
        .join(Conta, Conta.id == Transacao.conta_id)
        .outerjoin(TransacaoPagamento, TransacaoPagamento.transacao_id == Transacao.id)
        .where(Transacao.usuario_id == usuario_id, Transacao.eh_transferencia.is_(False))
    )


def _lancamento_de(r) -> Lancamento:
    """Linha de `_select_transacoes` → `Lancamento` (estorno de cartão vira DEBIT negativo)."""
    receita = r.tipo == "CREDIT" and not r.estorno
    return Lancamento(
        data=_aware(r.data),
        valor=-int(r.valor) if r.estorno else int(r.valor),
        tipo="DEBIT" if r.estorno else r.tipo,
        categoria=r.categoria,
        transacao_id=r.transacao_id,
        divisao_id=None,
        conta_id=r.conta_id,
        # Despesa: quem recebeu; receita: quem pagou. Descrição do usuário manda.
        contraparte=r.descricao_usuario
        or r.merchant_nome
        or (r.payer_nome if receita else r.receiver_nome)
        or r.description,
        meio=meio_de(r.conta_tipo, r.operation_type, r.metodo),
    )


def lancamentos_do_periodo(
    db: Session, usuario_id: int, ini: datetime, fim_excl: datetime
) -> list[Lancamento]:
    """Lançamentos do período sem transferências (§4.2) — base única de dashboard, abas de
    receitas/despesas e orçamento. Agregação em Python: resultado idêntico nos dois bancos."""
    stmt = _select_transacoes(usuario_id, categorias_renda(db, usuario_id)).where(
        Transacao.date >= ini, Transacao.date < fim_excl
    )
    out = [_lancamento_de(r) for r in db.execute(stmt)]
    parcelas = parcelas_divisao(usuario_id).where(
        DivisaoDespesa.data >= ini, DivisaoDespesa.data < fim_excl
    )
    out += [
        Lancamento(_aware(d), int(v), "DEBIT", c, None, div_id, None, desc, MEIO_DIVISAO)
        for div_id, c, d, v, desc in db.execute(parcelas).all()
    ]
    return out


def linhas_do_periodo(
    db: Session, usuario_id: int, ini: datetime, fim_excl: datetime
) -> list[tuple[datetime, int, str, str | None]]:
    """[(data aware, valor do usuário, 'DEBIT'|'CREDIT', categoria efetiva)] do período — a visão
    enxuta de `lancamentos_do_periodo` (estorno de cartão: DEBIT negativo)."""
    return [
        (x.data, x.valor, x.tipo, x.categoria)
        for x in lancamentos_do_periodo(db, usuario_id, ini, fim_excl)
    ]


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)  # SQLite devolve naive (UTC)
