"""Contratos explícitos: token write-only, identidade nunca editável pelo cliente."""

import re
from datetime import datetime, time

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class IdentidadeTelegram(BaseModel):
    usuario_id: str
    nome: str | None
    username: str | None


class TelegramRead(BaseModel):
    configurado: bool
    bot_username: str | None
    ativo: bool
    vinculado: bool
    identidade: IdentidadeTelegram | None
    candidato: IdentidadeTelegram | None
    solicitacao_id: str | None
    vinculo_expira_em: datetime | None
    notif_nao_revisadas: bool
    ultimo_envio_em: datetime | None
    erro: str | None
    sync_automatico: bool
    sync_horario: time
    proxima_rotina: datetime | None


class TelegramUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    notif_nao_revisadas: bool


class VinculoRead(BaseModel):
    solicitacao_id: str
    url: str
    expira_em: datetime


class VinculoConfirmar(BaseModel):
    model_config = ConfigDict(extra="forbid")
    solicitacao_id: str = Field(min_length=1, max_length=64)


class TelegramInstanciaRead(BaseModel):
    configurado: bool
    bot_username: str | None
    ativo: bool
    erro: str | None


class TelegramInstanciaUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str | None = Field(default=None, min_length=1, max_length=256)
    ativo: bool | None = None
    confirmar_troca_bot: bool | None = None

    @model_validator(mode="after")
    def campos_nao_nulos(self):
        for campo in {"ativo", "confirmar_troca_bot"} & self.model_fields_set:
            if getattr(self, campo) is None:
                raise ValueError(f"{campo} não pode ser nulo")
        return self

    @field_validator("token")
    @classmethod
    def token_seguro(cls, valor: str | None) -> str | None:
        if valor is not None and not re.fullmatch(r"[0-9]+:[A-Za-z0-9_-]+", valor):
            raise ValueError("token inválido")
        return valor
