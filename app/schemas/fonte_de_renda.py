"""Schemas de `fonte_de_renda` (CRUD completo do usuário)."""

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas import ORMModel

Tipo = Literal["fixa", "variavel"]
Recorrencia = Literal["mensal", "trimestral", "semestral", "anual", "irregular"]


class FonteDeRendaCreate(BaseModel):
    nome: str = Field(min_length=1, max_length=255)
    tipo: Tipo
    valor_estimado_centavos: int = Field(ge=0)
    recorrencia: Recorrencia
    fonte: str | None = Field(default=None, max_length=255)


class FonteDeRendaUpdate(BaseModel):
    """PATCH parcial — só os campos enviados são alterados."""

    nome: str | None = Field(default=None, min_length=1, max_length=255)
    tipo: Tipo | None = None
    valor_estimado_centavos: int | None = Field(default=None, ge=0)
    recorrencia: Recorrencia | None = None
    fonte: str | None = Field(default=None, max_length=255)


class FonteDeRendaRead(ORMModel):
    id: int
    usuario_id: int
    nome: str
    tipo: Tipo
    valor_estimado_centavos: int
    recorrencia: Recorrencia
    fonte: str | None
