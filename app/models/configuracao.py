"""Configuração global da instância (§4.11-otimização) — linha única (id=1), sem `UserOwnedMixin`
(não é posse de ninguém, é da instância inteira). Get-or-create fica no repositório
(`app/repositories/configuracao.py`).
"""

from datetime import time

from sqlalchemy import BigInteger, Boolean, String, Time
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin
from app.models.types import EncryptedStr


class ConfiguracaoSistema(TimestampMixin, Base):
    __tablename__ = "configuracao_sistema"

    id: Mapped[int] = mapped_column(primary_key=True)
    otimizar_transacoes_divisao: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    telegram_token_cifrado: Mapped[str | None] = mapped_column(EncryptedStr)
    telegram_bot_id: Mapped[str | None] = mapped_column(String(64))
    telegram_username: Mapped[str | None] = mapped_column(String(255))
    telegram_ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    telegram_offset: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    telegram_erro: Mapped[str | None] = mapped_column(String(80))
    telegram_url: Mapped[str | None] = mapped_column(String(1024))
    sync_automatico: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sync_horario: Mapped[time] = mapped_column(Time, nullable=False, default=time(8))
