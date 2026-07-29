"""Objetivos financeiros (§4.8, decisão #4). CRUD do usuário.

O valor guardado = soma dos saldos de `conta`/`investimento` vinculados (runtime, não coluna).
A regra 1:1-max (#4) mora no FK `objetivo_id` (coluna única) de `conta`/`investimento`.
"""

from sqlalchemy import BigInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UserOwnedMixin


class Objetivo(UserOwnedMixin, TimestampMixin, Base):
    __tablename__ = "objetivo"

    id: Mapped[int] = mapped_column(primary_key=True)
    titulo: Mapped[str] = mapped_column(String(255), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text)
    justificativa: Mapped[str | None] = mapped_column(Text)
    valor_alvo_centavos: Mapped[int] = mapped_column(BigInteger, nullable=False)
