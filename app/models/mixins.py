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

    Exceção única: `categoria` NÃO usa este mixin porque seu `usuario_id` é **nulável** (NULL = a
    taxonomia global do Pluggy; preenchido = categoria personalizada do usuário, §4.5). O
    isolamento dela é feito à mão no `CategoriaRepository`, não pelo mixin.
    """

    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False, index=True
    )
