"""Vínculo verificado por usuário e controle de execuções diárias do Telegram."""

from datetime import date, datetime, time

from sqlalchemy import Boolean, Date, DateTime, Integer, String, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UserOwnedMixin


class ConfigTelegram(UserOwnedMixin, TimestampMixin, Base):
    __tablename__ = "config_telegram"
    __table_args__ = (
        UniqueConstraint("usuario_id"),
        UniqueConstraint("telegram_usuario_id"),
        UniqueConstraint("chat_id"),
        UniqueConstraint("vinculo_hash"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[str | None] = mapped_column(String(64))  # após /start
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notif_nova_transacao: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notif_nao_revisadas: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    horario_1: Mapped[time | None] = mapped_column(Time)  # 2×/dia
    horario_2: Mapped[time | None] = mapped_column(Time)
    resumo_diario: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    resumo_semanal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dia_semana: Mapped[int | None] = mapped_column(Integer)  # 0=segunda … 6=domingo
    telegram_usuario_id: Mapped[str | None] = mapped_column(String(64))
    telegram_nome: Mapped[str | None] = mapped_column(String(255))
    telegram_username: Mapped[str | None] = mapped_column(String(255))
    vinculo_hash: Mapped[str | None] = mapped_column(String(64))
    solicitacao_id: Mapped[str | None] = mapped_column(String(64))
    vinculo_expira_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    candidato_id: Mapped[str | None] = mapped_column(String(64))
    candidato_nome: Mapped[str | None] = mapped_column(String(255))
    candidato_username: Mapped[str | None] = mapped_column(String(255))
    ultimo_teste_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ultimo_envio_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    erro: Mapped[str | None] = mapped_column(String(80))


class ExecucaoDiaria(UserOwnedMixin, TimestampMixin, Base):
    """Controle durável por usuário/dia; nunca contém mensagens financeiras."""

    __tablename__ = "execucao_diaria"
    __table_args__ = (UniqueConstraint("usuario_id", "data"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    data: Mapped[date] = mapped_column(Date, nullable=False)
    sync_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pendente")
    envio_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pendente")
    tentativas_sync: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tentativas_envio: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    proxima_tentativa: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    erro: Mapped[str | None] = mapped_column(String(80))
