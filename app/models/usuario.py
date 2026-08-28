"""Identidade e autenticação (§5.2). O fluxo de login/TOTP é da Fase 1; aqui só o modelo."""

from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.enums import TIPO_USUARIO, check_in
from app.models.mixins import TimestampMixin
from app.models.types import EncryptedStr


class Usuario(TimestampMixin, Base):
    __tablename__ = "usuario"
    __table_args__ = (check_in("tipo", TIPO_USUARIO, "tipo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)

    # Auth self-hosted (null no modo local).
    senha_hash: Mapped[str | None] = mapped_column(String(255))
    totp_secret_cifrado: Mapped[str | None] = mapped_column(EncryptedStr)  # cifrado §5.5
    # 2FA é opcional (§5.2): esta flag é o "quero código no login" do usuário — só tem efeito
    # junto de `totp_secret_cifrado` configurado (ver `totp_exigido_no_login`). Recuperação de
    # senha sempre exige o código, independente desta flag (é a prova de posse, não um extra).
    totp_login_habilitado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Tipo de conta (só faz sentido no self-hosted, §4.11): "completo" enxerga o app inteiro,
    # "divisao" só o módulo de divisão de contas (+ perfil/preferências). `ativo` bloqueia
    # login/sessão sem apagar histórico; `is_admin` é o dono da instância — quem gerencia os
    # outros usuários (criar/ativar/desativar/apagar), único por instância (criado no /setup).
    tipo: Mapped[str] = mapped_column(String(20), nullable=False, default="completo")
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Campos pessoais — todos opcionais (#6).
    data_nascimento: Mapped[date | None] = mapped_column(Date)
    salario_mensal_centavos: Mapped[int | None] = mapped_column(BigInteger)
    formacao: Mapped[str | None] = mapped_column(String(255))
    ocupacao: Mapped[str | None] = mapped_column(String(255))

    # Preferências do sistema — null = padrões do frontend (violeta / avatar 1).
    accent: Mapped[str | None] = mapped_column(String(20))
    avatar: Mapped[int | None] = mapped_column()

    # Data de corte da revisão (§4.3): transação ANTES dela tem a revisão **ignorada** — não é
    # marcada como revisada, só sai da fila. O Pluggy traz o histórico inteiro ao conectar a conta,
    # e ninguém quer revisar anos de lançamentos passados. null = sem corte, todo o histórico pede
    # revisão (comportamento anterior a este campo).
    revisao_desde: Mapped[date | None] = mapped_column(Date)

    # Token brapi.dev (preços/IBOV, §4.9) — cifrado em repouso (§5.5); nunca devolvido pela API.
    brapi_token_cifrado: Mapped[str | None] = mapped_column(EncryptedStr)

    sessoes: Mapped[list["Sessao"]] = relationship(
        back_populates="usuario", cascade="all, delete-orphan"
    )

    @property
    def brapi_token_configurado(self) -> bool:
        """Booleano p/ a API (o segredo nunca sai). Já decifrado no load, como `totp_secret`."""
        return bool(self.brapi_token_cifrado)

    @property
    def totp_configurado(self) -> bool:
        """Booleano p/ a API — mesmo padrão de `brapi_token_configurado`, segredo nunca sai."""
        return bool(self.totp_secret_cifrado)

    @property
    def totp_exigido_no_login(self) -> bool:
        """Fonte única de verdade sobre "o login pede código" — nunca confiar isoladamente na
        flag crua (defesa em profundidade caso o secret seja zerado sem resetar a flag)."""
        return self.totp_configurado and self.totp_login_habilitado


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
