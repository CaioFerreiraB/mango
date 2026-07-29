"""Divisão de contas (§4.11, decisão #7) — réplica reduzida do Splitwise.

Pareada (criador + outro), ambos da mesma instância. NÃO usa UserOwnedMixin: a posse é o
criador (`criado_por_usuario_id`); o repositório filtra por essa coluna (scope_column).
"""

from sqlalchemy import BigInteger, Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.enums import MODO_DIVISAO, check_in
from app.models.mixins import TimestampMixin


class DivisaoDespesa(TimestampMixin, Base):
    __tablename__ = "divisao_despesa"
    __table_args__ = (check_in("modo_divisao", MODO_DIVISAO, "modo_divisao"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    criado_por_usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False, index=True
    )
    outro_usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False, index=True
    )
    valor_centavos: Mapped[int] = mapped_column(BigInteger, nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text)
    categoria_id: Mapped[str | None] = mapped_column(
        ForeignKey("categoria.pluggy_id", ondelete="SET NULL"), index=True
    )
    modo_divisao: Mapped[str] = mapped_column(String(24), nullable=False)
    quitada: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
