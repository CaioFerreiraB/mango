"""Schemas de `objetivo` (§4.8). O Read é enriquecido com valor guardado e progresso, ambos
calculados em runtime (não são colunas) a partir dos saldos vinculados."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas import ORMModel


class ObjetivoCreate(BaseModel):
    titulo: str = Field(min_length=1, max_length=255)
    descricao: str | None = None
    justificativa: str | None = None
    valor_alvo_centavos: int = Field(ge=0)


class ObjetivoUpdate(BaseModel):
    titulo: str | None = Field(default=None, min_length=1, max_length=255)
    descricao: str | None = None
    justificativa: str | None = None
    valor_alvo_centavos: int | None = Field(default=None, ge=0)


class ObjetivoVinculo(BaseModel):
    """Uma conta ou investimento vinculado ao objetivo (para a UI de vínculo)."""

    tipo: Literal["conta", "investimento"]
    id: int
    nome: str | None
    saldo_centavos: int


class ObjetivoRead(ORMModel):
    id: int
    usuario_id: int
    titulo: str
    descricao: str | None
    justificativa: str | None
    valor_alvo_centavos: int
    criado_em: datetime
    atualizado_em: datetime
    # Calculados: soma dos saldos vinculados e razão guardado/alvo (teto 1.0).
    valor_guardado_centavos: int = 0
    progresso: float = 0.0


class ObjetivoDetalheRead(ObjetivoRead):
    vinculos: list[ObjetivoVinculo] = []
