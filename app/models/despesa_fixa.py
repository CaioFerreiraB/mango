"""Despesas fixas (docs/dev/despesas-fixas.md): contas recorrentes acompanhadas por vencimento.

`despesa_fixa` é a definição (valor + agenda); `despesa_fixa_ocorrencia` é cada vencimento
materializado (lazy) com o status guardado `aberta|paga|pulada`. "Atrasada" e "vence hoje" são
derivados de `aberta` + data — nunca gravados, para não precisar de job que vire status.
"""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.enums import FREQUENCIA, STATUS_OCORRENCIA, check_in
from app.models.mixins import TimestampMixin, UserOwnedMixin


class DespesaFixa(UserOwnedMixin, TimestampMixin, Base):
    __tablename__ = "despesa_fixa"
    __table_args__ = (
        check_in("frequencia", FREQUENCIA, "frequencia"),
        CheckConstraint("valor_centavos > 0", name="valor_positivo"),
        CheckConstraint("dia_vencimento BETWEEN 1 AND 31", name="dia_vencimento"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    descricao: Mapped[str] = mapped_column(String(255), nullable=False)
    valor_centavos: Mapped[int] = mapped_column(BigInteger, nullable=False)
    frequencia: Mapped[str] = mapped_column(String(16), nullable=False)
    dia_vencimento: Mapped[int] = mapped_column(Integer, nullable=False)
    # Âncora da agenda: o 1º vencimento é o `dia_vencimento` do mês de `inicio` (ou do seguinte).
    inicio: Mapped[date] = mapped_column(Date, nullable=False)
    fim: Mapped[date | None] = mapped_column(Date)  # só despesa temporária
    # Reativação: vencimentos antes daqui não são gerados (o período inativo não vira atraso).
    retomada_em: Mapped[date | None] = mapped_column(Date)
    ativa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class DespesaFixaOcorrencia(UserOwnedMixin, TimestampMixin, Base):
    __tablename__ = "despesa_fixa_ocorrencia"
    __table_args__ = (
        UniqueConstraint("despesa_fixa_id", "vencimento"),
        check_in("status", STATUS_OCORRENCIA, "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    despesa_fixa_id: Mapped[int] = mapped_column(
        ForeignKey("despesa_fixa.id", ondelete="CASCADE"), nullable=False, index=True
    )
    vencimento: Mapped[date] = mapped_column(Date, nullable=False)
    valor_centavos: Mapped[int] = mapped_column(BigInteger, nullable=False)  # snapshot
    status: Mapped[str] = mapped_column(String(8), nullable=False, default="aberta")
    pago_em: Mapped[date | None] = mapped_column(Date)
    # Dedup do Telegram (gravados ANTES do envio): "vence hoje" sai 1×; atraso, 1× por dia.
    aviso_hoje_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    aviso_atraso_em: Mapped[date | None] = mapped_column(Date)
