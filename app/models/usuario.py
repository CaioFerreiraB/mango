"""Identidade e autenticação (§5.2). O fluxo de login/TOTP é da Fase 1; aqui só o modelo."""

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin
from app.models.types import EncryptedStr


class Usuario(TimestampMixin, Base):
    __tablename__ = "usuario"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)

    # Auth self-hosted (null no modo local).
    senha_hash: Mapped[str | None] = mapped_column(String(255))
    totp_secret_cifrado: Mapped[str | None] = mapped_column(EncryptedStr)  # cifrado §5.5

    # Campos pessoais — todos opcionais (#6).
    data_nascimento: Mapped[date | None] = mapped_column(Date)
    salario_mensal_centavos: Mapped[int | None] = mapped_column(BigInteger)
    formacao: Mapped[str | None] = mapped_column(String(255))
    ocupacao: Mapped[str | None] = mapped_column(String(255))

    # Preferências do sistema — null = padrões do frontend (violeta / avatar 1).
    accent: Mapped[str | None] = mapped_column(String(20))
    avatar: Mapped[int | None] = mapped_column()

    # Token brapi.dev (preços/IBOV, §4.9) — cifrado em repouso (§5.5); nunca devolvido pela API.
    brapi_token_cifrado: Mapped[str | None] = mapped_column(EncryptedStr)

    sessoes: Mapped[list["Sessao"]] = relationship(
        back_populates="usuario", cascade="all, delete-orphan"
    )

    @property
    def brapi_token_configurado(self) -> bool:
        """Booleano p/ a API (o segredo nunca sai). Já decifrado no load, como `totp_secret`."""
        return bool(self.brapi_token_cifrado)


class Sessao(Base):
    """Sessão no servidor (#13): ID opaco (não-JWT), revogável (logout / sair de todos)."""

    __tablename__ = "sessao"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # ID opaco aleatório
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False, index=True
    )
    csrf_token: Mapped[str] = mapped_column(String(64), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revogada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user_agent: Mapped[str | None] = mapped_column(String(512))
    ip: Mapped[str | None] = mapped_column(String(64))

    usuario: Mapped["Usuario"] = relationship(back_populates="sessoes")
