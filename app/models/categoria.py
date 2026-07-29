"""Categoria — espelho read-only de `GET /categories` (§4.5).

ÚNICA entidade de domínio SEM `usuario_id`: taxonomia global compartilhada. Hierarquia
≤3 níveis via auto-FK `parent_id`. Populada por seed (idempotente). `POST /categories`
do Pluggy retorna 405 → não criamos categorias novas; override é por transação.
"""

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Categoria(Base):
    __tablename__ = "categoria"

    # A maioria tem 8 dígitos, mas o 3º nível chega a 9 (ex.: 200300000) — 16 dá folga.
    # Postgres impõe o VARCHAR(n) (o SQLite não), então subdimensionar quebra o seed no PG.
    pluggy_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)  # inglês
    description_translated: Mapped[str | None] = mapped_column(String(255))  # pt-BR
    parent_id: Mapped[str | None] = mapped_column(
        ForeignKey("categoria.pluggy_id", ondelete="RESTRICT"), index=True
    )
