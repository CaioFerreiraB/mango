"""Divisão de contas (§4.11, decisão #7) — réplica reduzida do Splitwise.

Cabeçalho (`DivisaoDespesa`) + participantes (`DivisaoParticipante`), suportando N pessoas por
despesa (não mais pareado 1:1). NÃO usa `UserOwnedMixin`: a posse é de quem criou
(`criado_por_usuario_id`), mas a *visibilidade* é mais ampla — criador, pagador ou qualquer
participante — por isso o repositório (`app/repositories/divisao.py`) não é o genérico
`UserScopedRepository`.
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.enums import MODO_DIVISAO, check_in
from app.models.mixins import TimestampMixin


class DivisaoDespesa(TimestampMixin, Base):
    __tablename__ = "divisao_despesa"
    __table_args__ = (
        check_in("modo_divisao", MODO_DIVISAO, "modo_divisao"),
        CheckConstraint("NOT (transacao_id IS NOT NULL AND sem_transacao)", name="vinculo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    criado_por_usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False, index=True
    )
    pago_por_usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False, index=True
    )
    descricao: Mapped[str | None] = mapped_column(Text)
    categoria_id: Mapped[str | None] = mapped_column(
        ForeignKey("categoria.pluggy_id", ondelete="SET NULL"), index=True
    )
    valor_total_centavos: Mapped[int] = mapped_column(BigInteger, nullable=False)
    modo_divisao: Mapped[str] = mapped_column(String(24), nullable=False)
    quitada: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    arquivada: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Quando a despesa aconteceu (ordena a lista de transações e cai no mês do orçamento).
    # Vincular a uma transação copia a data dela.
    data: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Transação bancária do PAGADOR que corresponde à despesa (1 ↔ 1). Orçamento/dashboard do
    # pagador contam só a parte dele nessa transação. SET NULL: resync que apaga a transação
    # devolve a divisão à pendência.
    transacao_id: Mapped[int | None] = mapped_column(
        ForeignKey("transacao.id", ondelete="SET NULL"), unique=True
    )
    # "Paguei fora do banco": sem transação a vincular — sai da pendência e a parte do pagador
    # conta como lançamento próprio, igual à parcela de quem não pagou.
    sem_transacao: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class DivisaoParticipante(Base):
    """Uma linha por pessoa que participa da despesa (inclui quem pagou no modo `igualmente`)."""

    __tablename__ = "divisao_participante"
    __table_args__ = (UniqueConstraint("divisao_id", "usuario_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    divisao_id: Mapped[int] = mapped_column(
        ForeignKey("divisao_despesa.id", ondelete="CASCADE"), nullable=False, index=True
    )
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False, index=True
    )
    valor_centavos: Mapped[int] = mapped_column(BigInteger, nullable=False)
