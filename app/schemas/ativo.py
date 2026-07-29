"""Schemas de `ativo` (§4.9): agrupa compras de renda fixa sob um nome editável."""

from pydantic import BaseModel, Field

from app.models.ativo import Ativo
from app.schemas.auto import read_model

AtivoRead = read_model(Ativo)


class AtivoCreate(BaseModel):
    nome: str = Field(min_length=1, max_length=255)


class AtivoUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=255)
