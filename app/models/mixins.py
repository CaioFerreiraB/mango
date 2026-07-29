"""Mixins comuns: timestamps da aplicação e posse por usuário (isolamento §5.2)."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    """`criado_em`/`atualizado_em` da aplicação (distintos dos timestamps do Pluggy)."""

    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class UserOwnedMixin:
    """`usuario_id` em toda entidade de domínio — base do isolamento por repositório.

    Exceção única: `categoria` (referência global read-only) NÃO usa este mixin.
    """

    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False, index=True
    )
