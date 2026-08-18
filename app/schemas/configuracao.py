"""Schemas de `configuracao_sistema` (§4.11-otimização) — config global da instância."""

from pydantic import BaseModel

from app.schemas import ORMModel


class ConfiguracaoSistemaRead(ORMModel):
    otimizar_transacoes_divisao: bool


class ConfiguracaoSistemaUpdate(BaseModel):
    otimizar_transacoes_divisao: bool
