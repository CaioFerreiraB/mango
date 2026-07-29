"""Investimentos (§4.9, decisão #5) — `GET /investments`. Valores já calculados pelo Pluggy.

Campos variam por tipo → maioria nullable. Cotação/quantidade/taxas % usam NUMERIC
(precisão), não centavos (modelo §3). `type`/`subtype` são string livre (conjunto aberto
do Pluggy) — sem CHECK. Único campo do usuário: `objetivo_id` (1:1-max #4).
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UserOwnedMixin


class Investimento(UserOwnedMixin, TimestampMixin, Base):
    __tablename__ = "investimento"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("item_pluggy.id", ondelete="CASCADE"), nullable=False, index=True
    )
    objetivo_id: Mapped[int | None] = mapped_column(
        ForeignKey("objetivo.id", ondelete="SET NULL"), index=True
    )
    # Ativo do usuário que agrupa esta posição (renda fixa; auto por ISIN/nome + ajuste manual).
    # Campo do usuário — o re-sync não sobrescreve (pop no upsert, como `objetivo_id`).
    ativo_id: Mapped[int | None] = mapped_column(
        ForeignKey("ativo.id", ondelete="SET NULL"), index=True
    )
    pluggy_investment_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    nome: Mapped[str | None] = mapped_column(String(255))
    numero: Mapped[str | None] = mapped_column(String(64))
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    subtype: Mapped[str | None] = mapped_column(String(32))

    saldo_centavos: Mapped[int] = mapped_column(BigInteger, nullable=False)
    amount_centavos: Mapped[int | None] = mapped_column(BigInteger)  # bruto atual
    amount_original_centavos: Mapped[int | None] = mapped_column(BigInteger)  # investido
    taxes_centavos: Mapped[int | None] = mapped_column(BigInteger)  # IR (consumido #5)
    taxes2_centavos: Mapped[int | None] = mapped_column(BigInteger)  # IOF (consumido #5)
    amount_profit_centavos: Mapped[int | None] = mapped_column(BigInteger)
    amount_withdrawal_centavos: Mapped[int | None] = mapped_column(BigInteger)

    quantity: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))  # fracionária
    value_unitario: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))  # cotação

    code: Mapped[str | None] = mapped_column(String(32))  # ticker
    isin: Mapped[str | None] = mapped_column(String(20))
    issuer: Mapped[str | None] = mapped_column(String(255))
    issuer_cnpj: Mapped[str | None] = mapped_column(String(20))

    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    issue_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    purchase_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    grace_period_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    rate: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    rate_type: Mapped[str | None] = mapped_column(String(32))
    rate_periodicity: Mapped[str | None] = mapped_column(String(32))
    fixed_annual_rate: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    annual_rate: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    last_month_rate: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    last_twelve_months_rate: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    tax_exempt: Mapped[bool | None] = mapped_column(Boolean)

    owner: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str | None] = mapped_column(String(32))
    instituicao_emissora_nome: Mapped[str | None] = mapped_column(String(255))
    instituicao_emissora_numero: Mapped[str | None] = mapped_column(String(64))

    pluggy_criado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pluggy_atualizado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class InvestimentoTransacao(Base):
    """N por investimento — `GET /investments/{id}/transactions` (proventos/movimentos, §4.9)."""

    __tablename__ = "investimento_transacao"

    id: Mapped[int] = mapped_column(primary_key=True)
    investimento_id: Mapped[int] = mapped_column(
        ForeignKey("investimento.id", ondelete="CASCADE"), nullable=False, index=True
    )
    pluggy_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    # Conjunto aberto do Pluggy (BUY/SELL + DIVIDEND/TRANSFER/… em dados reais) — string
    # livre nullable, mesmo racional de `Investimento.type`. Provento = CREDIT não-BUY/SELL.
    type: Mapped[str | None] = mapped_column(String(32))
    movement_type: Mapped[str | None] = mapped_column(String(32))  # CREDIT | DEBIT
    amount_centavos: Mapped[int] = mapped_column(BigInteger, nullable=False)
    value_unitario: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    net_amount_centavos: Mapped[int | None] = mapped_column(BigInteger)
    expenses_centavos: Mapped[int | None] = mapped_column(BigInteger)
    trade_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    description: Mapped[str | None] = mapped_column(String(255))
    brokerage_number: Mapped[str | None] = mapped_column(String(64))
    # Aporte informado à mão pelo usuário (não veio do Pluggy): entra no custo médio como um BUY e
    # é o único tipo de movimento editável/removível. `pluggy_id` fica NULL → o sync não o toca.
    manual: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
