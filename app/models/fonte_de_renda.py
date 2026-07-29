"""Fontes de renda (§4.1, decisão #17) — entidade própria, CRUD do usuário."""

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.enums import RECORRENCIA, TIPO_FONTE, check_in
from app.models.mixins import TimestampMixin, UserOwnedMixin


class FonteDeRenda(UserOwnedMixin, TimestampMixin, Base):
    __tablename__ = "fonte_de_renda"
    __table_args__ = (
        check_in("tipo", TIPO_FONTE, "tipo"),
        check_in("recorrencia", RECORRENCIA, "recorrencia"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    tipo: Mapped[str] = mapped_column(String(16), nullable=False)  # fixa | variavel
    valor_estimado_centavos: Mapped[int] = mapped_column(BigInteger, nullable=False)
    recorrencia: Mapped[str] = mapped_column(String(16), nullable=False)
    fonte: Mapped[str | None] = mapped_column(String(255))  # empregador/cliente
