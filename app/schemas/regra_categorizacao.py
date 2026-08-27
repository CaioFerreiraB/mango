"""Schemas de `regra_categorizacao` (§4.5)."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.models.categoria import RegraCategorizacao
from app.schemas.auto import read_model

TipoMatch = Literal["exato", "contem"]

# `texto_normalizado` é derivado (minúsculo/sem acento) e só serve ao casamento — não é API.
# `tipo_match` é `String(8)` no model, então o inferido seria `str`; o override devolve o enum ao
# OpenAPI e, com ele, ao cliente TS gerado.
RegraCategorizacaoRead = read_model(
    RegraCategorizacao,
    exclude=("texto_normalizado",),
    overrides={"tipo_match": TipoMatch},
)

# Mínimo de 3 é defesa, não estética: uma regra "contém" de 1–2 caracteres casaria quase toda
# transação e recategorizaria o histórico inteiro de uma vez.
TEXTO_MIN = 3
TEXTO_MAX = 120


def _texto_limpo(v: str) -> str:
    limpo = " ".join(v.split())
    if len(limpo) < TEXTO_MIN:
        raise ValueError(f"o texto precisa de pelo menos {TEXTO_MIN} caracteres")
    return limpo


class RegraCategorizacaoCreate(BaseModel):
    texto: str = Field(min_length=TEXTO_MIN, max_length=TEXTO_MAX)
    tipo_match: TipoMatch
    categoria_id: str = Field(max_length=16)

    @field_validator("texto")
    @classmethod
    def _limpar(cls, v: str) -> str:
        return _texto_limpo(v)


class RegraCategorizacaoUpdate(BaseModel):
    texto: str | None = Field(default=None, min_length=TEXTO_MIN, max_length=TEXTO_MAX)
    tipo_match: TipoMatch | None = None
    categoria_id: str | None = Field(default=None, max_length=16)

    @field_validator("texto")
    @classmethod
    def _limpar(cls, v: str | None) -> str | None:
        return _texto_limpo(v) if v is not None else None
