"""Acesso de agentes via MCP (docs/mcp.md): um por usuário, ligado/desligado na aba "MCP".

O token é guardado duas vezes, para dois usos: `token_hash` (sha256, em claro e único) é a chave
da busca na autenticação — coluna cifrada não serve para igualdade (Fernet não é determinístico);
`token_cifrado` existe só para o usuário revelar o token de novo na aba, como o token brapi.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.enums import ESCOPO_MCP, check_in
from app.models.mixins import TimestampMixin, UserOwnedMixin
from app.models.types import EncryptedStr


class AcessoMcp(UserOwnedMixin, TimestampMixin, Base):
    __tablename__ = "acesso_mcp"
    __table_args__ = (UniqueConstraint("usuario_id"), check_in("escopo", ESCOPO_MCP, "escopo"))

    id: Mapped[int] = mapped_column(primary_key=True)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    escopo: Mapped[str] = mapped_column(String(10), nullable=False, default="leitura")
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    token_cifrado: Mapped[str] = mapped_column(EncryptedStr, nullable=False)
    token_gerado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ultimo_uso_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
