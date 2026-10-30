"""Schema do resumo de sincronização (§4.3) — realimenta o toast da UI."""

from datetime import time

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.schemas import ORMModel


class ResumoSyncRead(BaseModel):
    itens: int
    contas: int
    transacoes: int
    transacoes_novas: int
    investimentos: int


class ConfiguracaoSyncRead(ORMModel):
    sync_automatico: bool
    sync_horario: time


class ConfiguracaoSyncUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sync_automatico: bool | None = None
    sync_horario: time | None = None

    @model_validator(mode="after")
    def campos_nao_nulos(self):
        if any(getattr(self, campo) is None for campo in self.model_fields_set):
            raise ValueError("a configuração não pode ser nula")
        return self

    @field_validator("sync_horario")
    @classmethod
    def horario_local(cls, valor: time | None) -> time | None:
        if valor is None:
            return None
        if valor.tzinfo is not None or valor.second or valor.microsecond:
            raise ValueError("use um horário HH:MM de São Paulo")
        return valor
