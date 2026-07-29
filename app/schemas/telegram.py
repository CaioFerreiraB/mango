"""Schemas de `config_telegram` (§4.12)."""

from datetime import time

from pydantic import BaseModel, Field

from app.models.telegram import ConfigTelegram
from app.schemas.auto import read_model

ConfigTelegramRead = read_model(ConfigTelegram)


class ConfigTelegramCreate(BaseModel):
    chat_id: str | None = Field(default=None, max_length=64)
    ativo: bool = False
    notif_nova_transacao: bool = False
    notif_nao_revisadas: bool = False
    horario_1: time | None = None
    horario_2: time | None = None
    resumo_diario: bool = False
    resumo_semanal: bool = False
    dia_semana: int | None = Field(default=None, ge=0, le=6)


class ConfigTelegramUpdate(BaseModel):
    chat_id: str | None = Field(default=None, max_length=64)
    ativo: bool | None = None
    notif_nova_transacao: bool | None = None
    notif_nao_revisadas: bool | None = None
    horario_1: time | None = None
    horario_2: time | None = None
    resumo_diario: bool | None = None
    resumo_semanal: bool | None = None
    dia_semana: int | None = Field(default=None, ge=0, le=6)
