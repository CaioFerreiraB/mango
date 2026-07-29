"""Snapshot diário de valor por investimento (§4.9).

A Pluggy só expõe o valor atual; sem histórico de cotação não há reconstrução retroativa
(diferente de `saldo_diario` de conta) — a série da carteira acumula daqui pra frente via
estes snapshots (renda variável com ticker ganha passado via brapi, no serviço). Upsert
idempotente por (investimento, data); `valor_centavos` = `amount_centavos` ?? `saldo_centavos`.
"""

from datetime import date

from sqlalchemy import BigInteger, Date, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import UserOwnedMixin


class InvestimentoSaldoDiario(UserOwnedMixin, Base):
    __tablename__ = "investimento_saldo_diario"
    __table_args__ = (
        UniqueConstraint("investimento_id", "data", name="uq_investimento_saldo_diario_inv_data"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    investimento_id: Mapped[int] = mapped_column(
        ForeignKey("investimento.id", ondelete="CASCADE"), nullable=False, index=True
    )
    data: Mapped[date] = mapped_column(Date, nullable=False)  # dia civil no fuso SP
    valor_centavos: Mapped[int] = mapped_column(BigInteger, nullable=False)
