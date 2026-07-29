"""Snapshot diário de saldo por conta.

A Pluggy só expõe o saldo atual; o histórico dia-a-dia é obtido por reconstrução (saldo atual −
transações posteriores) e, daqui pra frente, por estes snapshots — verdade quando presentes
(ver `docs/dev/descoberta-saldo-diario-e-imagem-cartao.md`). Upsert idempotente por (conta, data).
"""

from datetime import date

from sqlalchemy import BigInteger, Date, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import UserOwnedMixin


class SaldoDiario(UserOwnedMixin, Base):
    __tablename__ = "saldo_diario"
    __table_args__ = (UniqueConstraint("conta_id", "data", name="uq_saldo_diario_conta_data"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    conta_id: Mapped[int] = mapped_column(
        ForeignKey("conta.id", ondelete="CASCADE"), nullable=False, index=True
    )
    data: Mapped[date] = mapped_column(Date, nullable=False)  # dia civil no fuso SP
    saldo_centavos: Mapped[int] = mapped_column(BigInteger, nullable=False)
