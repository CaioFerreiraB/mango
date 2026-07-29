"""Schemas Pydantic (validação de fronteira; fonte de verdade da API/OpenAPI)."""

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    """Base p/ schemas de leitura — lê direto dos objetos ORM."""

    model_config = ConfigDict(from_attributes=True)
