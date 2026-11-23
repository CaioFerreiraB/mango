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

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.models.categoria import Categoria
from app.models.divisao import DivisaoDespesa, DivisaoParticipante
from app.models.transacao import Transacao
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


def linhas_do_periodo(
    db: Session, usuario_id: int, ini: datetime, fim_excl: datetime
) -> list[tuple[datetime, int, str, str | None]]:
    """[(data aware, valor ≥ 0 do usuário, 'DEBIT'|'CREDIT', categoria efetiva)] do período,
    sem transferências (§4.2). Agregação em Python: resultado idêntico nos dois bancos."""
    transacoes = db.execute(
        com_divisao(
            com_assinatura(
                select(
                    Transacao.date,
                    VALOR_USUARIO,
                    Transacao.type,
                    expr_categoria_efetiva(usuario_id),
                ),
                usuario_id,
            )
        ).where(
            Transacao.usuario_id == usuario_id,
            Transacao.date >= ini,
            Transacao.date < fim_excl,
            Transacao.eh_transferencia.is_(False),
        )
    ).all()
    parcelas = parcelas_divisao(usuario_id).where(
        DivisaoDespesa.data >= ini, DivisaoDespesa.data < fim_excl
    )
    divisoes = db.execute(parcelas).all()
    linhas = [(_aware(d), int(v), t, c) for d, v, t, c in transacoes]
    linhas += [(_aware(d), int(v), "DEBIT", c) for _, c, d, v in divisoes]
    return linhas


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)  # SQLite devolve naive (UTC)
