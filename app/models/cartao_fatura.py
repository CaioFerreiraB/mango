"""Detalhes de conta bancária / cartão e faturas (§4.2). Dados do Pluggy.

As tabelas-detalhe 1:1 (`conta_bancaria`, `cartao`) e as filhas de fatura NÃO carregam
`usuario_id` — são alcançadas pela conta/fatura-pai (que é user-scoped). `fatura` é
entidade de topo e carrega `usuario_id`.
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UserOwnedMixin


class ContaBancaria(Base):
    """1:1 com conta BANK — `accounts.json.bankData`."""

    __tablename__ = "conta_bancaria"

    conta_id: Mapped[int] = mapped_column(
        ForeignKey("conta.id", ondelete="CASCADE"), primary_key=True
    )
    transfer_number: Mapped[str | None] = mapped_column(String(64))
    closing_balance_centavos: Mapped[int | None] = mapped_column(BigInteger)
    automatically_invested_balance_centavos: Mapped[int | None] = mapped_column(BigInteger)
    overdraft_contracted_limit_centavos: Mapped[int | None] = mapped_column(BigInteger)
    overdraft_used_limit_centavos: Mapped[int | None] = mapped_column(BigInteger)
    unarranged_overdraft_amount_centavos: Mapped[int | None] = mapped_column(BigInteger)
    has_reserved_balance: Mapped[bool | None] = mapped_column(Boolean)


class ContaSaldoReservado(Base):
    """N por conta_bancaria — "caixinhas" (`bankData.reservedBalances[]`). Baixa prioridade."""

    __tablename__ = "conta_saldo_reservado"

    id: Mapped[int] = mapped_column(primary_key=True)
    conta_bancaria_id: Mapped[int] = mapped_column(
        ForeignKey("conta_bancaria.conta_id", ondelete="CASCADE"), nullable=False, index=True
    )
    nome: Mapped[str | None] = mapped_column(String(255))
    identificacao: Mapped[str | None] = mapped_column(String(255))
    valor_centavos: Mapped[int | None] = mapped_column(BigInteger)
    rem_indexer: Mapped[str | None] = mapped_column(String(32))
    rem_rate_type: Mapped[str | None] = mapped_column(String(32))
    rem_pre_fixed_rate: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    rem_periodicity: Mapped[str | None] = mapped_column(String(32))


class Cartao(Base):
    """1:1 com conta CREDIT — `accounts.json.creditData`."""

    __tablename__ = "cartao"

    conta_id: Mapped[int] = mapped_column(
        ForeignKey("conta.id", ondelete="CASCADE"), primary_key=True
    )
    level: Mapped[str | None] = mapped_column(String(32))
    brand: Mapped[str | None] = mapped_column(String(32))
    brand_additional_info: Mapped[str | None] = mapped_column(String(255))
    balance_close_date: Mapped[date | None] = mapped_column(Date)  # fechamento
    balance_due_date: Mapped[date | None] = mapped_column(Date)  # vencimento
    credit_limit_centavos: Mapped[int | None] = mapped_column(BigInteger)
    available_credit_limit_centavos: Mapped[int | None] = mapped_column(BigInteger)
    balance_foreign_currency_centavos: Mapped[int | None] = mapped_column(BigInteger)
    minimum_payment_centavos: Mapped[int | None] = mapped_column(BigInteger)
    is_limit_flexible: Mapped[bool | None] = mapped_column(Boolean)
    holder_type: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str | None] = mapped_column(String(32))


class Fatura(UserOwnedMixin, TimestampMixin, Base):
    """Fatura do cartão (`bills`). Competência × caixa (§4.2, #8)."""

    __tablename__ = "fatura"

    id: Mapped[int] = mapped_column(primary_key=True)
    cartao_id: Mapped[int] = mapped_column(
        ForeignKey("cartao.conta_id", ondelete="CASCADE"), nullable=False, index=True
    )
    pluggy_bill_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    total_amount_centavos: Mapped[int] = mapped_column(BigInteger, nullable=False)
    total_amount_currency_code: Mapped[str | None] = mapped_column(String(3))
    minimum_payment_centavos: Mapped[int | None] = mapped_column(BigInteger)
    allows_installments: Mapped[bool | None] = mapped_column(Boolean)


class FaturaEncargo(Base):
    """N por fatura — `bills.financeCharges[]` (IOF, juros, multa)."""

    __tablename__ = "fatura_encargo"

    id: Mapped[int] = mapped_column(primary_key=True)
    fatura_id: Mapped[int] = mapped_column(
        ForeignKey("fatura.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tipo: Mapped[str] = mapped_column(String(64), nullable=False)
    valor_centavos: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency_code: Mapped[str | None] = mapped_column(String(3))
    additional_info: Mapped[str | None] = mapped_column(String(255))


class FaturaPagamento(Base):
    """N por fatura — `bills.payments[]` (shape a confirmar; veio vazio na captura)."""

    __tablename__ = "fatura_pagamento"

    id: Mapped[int] = mapped_column(primary_key=True)
    fatura_id: Mapped[int] = mapped_column(
        ForeignKey("fatura.id", ondelete="CASCADE"), nullable=False, index=True
    )
    valor_centavos: Mapped[int | None] = mapped_column(BigInteger)
    data: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
