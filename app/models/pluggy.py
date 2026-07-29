"""Conexões Pluggy (§4.3, §5.5): instituição, credencial (app do usuário) e item (conexão).

Credenciais e itemId são sensíveis → colunas cifradas em repouso (§5.5, #10).
`apiKey`/`connectToken` são efêmeros (runtime) e NÃO são persistidos.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UserOwnedMixin
from app.models.types import EncryptedStr


class Instituicao(UserOwnedMixin, TimestampMixin, Base):
    """Instituição (derivada do connector do Pluggy). Conta referencia instituição.

    `logo_url` só é preenchido no vínculo manual (a partir do `imageUrl` do connector); a
    instituição original do sync ("meu Pluggy") fica sem logo.
    """

    __tablename__ = "instituicao"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    pluggy_connector_id: Mapped[int | None] = mapped_column(Integer)
    logo_url: Mapped[str | None] = mapped_column(String(1024))


class CredencialPluggy(UserOwnedMixin, TimestampMixin, Base):
    """O app do Pluggy do usuário (um por usuário, nível gratuito). Nunca lido em claro pela API."""

    __tablename__ = "credencial_pluggy"
    # 1 app por usuário. Sem `name=` explícito → usa a naming_convention
    # (uq_credencial_pluggy_usuario_id); um nome como "usuario" colidiria com a
    # tabela `usuario` no Postgres (índices e tabelas dividem o mesmo namespace).
    __table_args__ = (UniqueConstraint("usuario_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id_cifrado: Mapped[str] = mapped_column(EncryptedStr, nullable=False)
    client_secret_cifrado: Mapped[str] = mapped_column(EncryptedStr, nullable=False)

    itens: Mapped[list["ItemPluggy"]] = relationship(
        back_populates="credencial", cascade="all, delete-orphan"
    )


class ItemPluggy(UserOwnedMixin, TimestampMixin, Base):
    """Uma conexão (Meu Pluggy). Várias contas penduram num item."""

    __tablename__ = "item_pluggy"

    id: Mapped[int] = mapped_column(primary_key=True)
    credencial_id: Mapped[int] = mapped_column(
        ForeignKey("credencial_pluggy.id", ondelete="CASCADE"), nullable=False, index=True
    )
    pluggy_item_id: Mapped[str] = mapped_column(EncryptedStr, nullable=False)  # cifrado §5.5
    connector_id: Mapped[int | None] = mapped_column(Integer)
    connector_nome: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str | None] = mapped_column(String(64))
    status_detalhe: Mapped[str | None] = mapped_column(String(255))
    ultimo_sync_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    credencial: Mapped["CredencialPluggy"] = relationship(back_populates="itens")
