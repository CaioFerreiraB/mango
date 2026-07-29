"""Orçamentos por categoria (§4.6, decisão #20). CRUD do usuário.

Regra #20 (soma das subcategorias ≤ categoria) é validada no service `orcamento`.
`orcamento_mensal` é materializado de `orcamento` e editável por mês (base dos alertas).
"""

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UserOwnedMixin


class Orcamento(UserOwnedMixin, TimestampMixin, Base):
    __tablename__ = "orcamento"
    __table_args__ = (UniqueConstraint("usuario_id", "categoria_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    categoria_id: Mapped[str] = mapped_column(
        ForeignKey("categoria.pluggy_id", ondelete="RESTRICT"), nullable=False, index=True
    )
    limite_padrao_centavos: Mapped[int] = mapped_column(BigInteger, nullable=False)
    recorrente: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class OrcamentoMensal(UserOwnedMixin, TimestampMixin, Base):
    __tablename__ = "orcamento_mensal"
    __table_args__ = (UniqueConstraint("usuario_id", "categoria_id", "ano", "mes"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    orcamento_id: Mapped[int] = mapped_column(
        ForeignKey("orcamento.id", ondelete="CASCADE"), nullable=False, index=True
    )
    categoria_id: Mapped[str] = mapped_column(
        ForeignKey("categoria.pluggy_id", ondelete="RESTRICT"), nullable=False, index=True
    )
    ano: Mapped[int] = mapped_column(Integer, nullable=False)
    mes: Mapped[int] = mapped_column(Integer, nullable=False)
    limite_centavos: Mapped[int] = mapped_column(BigInteger, nullable=False)
    editado_manualmente: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
