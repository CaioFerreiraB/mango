"""Estado durável da integração: segredos de conteúdo cifrados, credenciais só por hash."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UserOwnedMixin
from app.models.types import EncryptedStr


class ConfigIntegracao(Base):
    __tablename__ = "config_integracao"
    id: Mapped[int] = mapped_column(primary_key=True)
    miniapp_ativo: Mapped[bool] = mapped_column(Boolean, default=False)
    url: Mapped[str | None] = mapped_column(String(1024))
    ia_ativa: Mapped[bool] = mapped_column(Boolean, default=False)
    provedor: Mapped[str] = mapped_column(String(32), default="openai_compatible")
    endpoint: Mapped[str | None] = mapped_column(String(1024))
    chave: Mapped[str | None] = mapped_column(EncryptedStr)
    modelo: Mapped[str | None] = mapped_column(String(255))
    limite_usuario: Mapped[int] = mapped_column(Integer, default=50)
    limite_instancia: Mapped[int] = mapped_column(Integer, default=500)
    validado: Mapped[bool] = mapped_column(Boolean, default=False)


class PreferenciaIa(UserOwnedMixin, Base):
    __tablename__ = "preferencia_ia"
    id: Mapped[int] = mapped_column(primary_key=True)
    __table_args__ = (UniqueConstraint("usuario_id"),)
    ativa: Mapped[bool] = mapped_column(Boolean, default=False)


class TrabalhoTelegram(UserOwnedMixin, TimestampMixin, Base):
    __tablename__ = "trabalho_telegram"
    __table_args__ = (UniqueConstraint("bot_id", "update_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    bot_id: Mapped[str] = mapped_column(String(64))
    update_id: Mapped[str] = mapped_column(String(64))
    chat_id: Mapped[str] = mapped_column(String(64))
    evento: Mapped[str | None] = mapped_column(EncryptedStr)
    status: Mapped[str] = mapped_column(String(24), default="pendente")
    erro: Mapped[str | None] = mapped_column(String(80))
    ia_aceita: Mapped[bool] = mapped_column(Boolean, default=False)


class CredencialIntegracao(UserOwnedMixin, Base):
    __tablename__ = "credencial_integracao"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    tipo: Mapped[str] = mapped_column(String(16))
    escopo: Mapped[str] = mapped_column(String(16))
    bot_id: Mapped[str] = mapped_column(String(64))
    telegram_id: Mapped[str] = mapped_column(String(64))
    trabalho_id: Mapped[int | None] = mapped_column(ForeignKey("trabalho_telegram.id"))
    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revogada: Mapped[bool] = mapped_column(Boolean, default=False)


class MensagemIa(UserOwnedMixin, TimestampMixin, Base):
    __tablename__ = "mensagem_ia"
    trabalho_id: Mapped[int] = mapped_column(ForeignKey("trabalho_telegram.id"))
    id: Mapped[int] = mapped_column(primary_key=True)
    papel: Mapped[str] = mapped_column(String(16))
    conteudo: Mapped[str] = mapped_column(EncryptedStr)


class OperacaoIntegracao(UserOwnedMixin, TimestampMixin, Base):
    __tablename__ = "operacao_integracao"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    trabalho_id: Mapped[int | None] = mapped_column(ForeignKey("trabalho_telegram.id"))
    tipo: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(24), default="pendente")
    payload: Mapped[str] = mapped_column(EncryptedStr)
    resultado: Mapped[str | None] = mapped_column(EncryptedStr)
    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
