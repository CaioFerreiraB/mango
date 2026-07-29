"""Configuração do Telegram (§4.12). Entidade modelada na Fase 0; notificações = Fase 4.

`chat_id` é capturado após o `/start` do usuário (o bot não inicia conversa sozinho).
"""

from datetime import time

from sqlalchemy import Boolean, Integer, String, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UserOwnedMixin


class ConfigTelegram(UserOwnedMixin, TimestampMixin, Base):
    __tablename__ = "config_telegram"
    __table_args__ = (UniqueConstraint("usuario_id"),)

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
