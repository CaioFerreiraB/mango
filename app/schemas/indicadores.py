"""Schemas de indicadores de mercado (§4.9): lista disponível + séries normalizadas."""

from datetime import date

from pydantic import BaseModel


class IndicadorInfo(BaseModel):
    codigo: str  # cdi | selic | ipca | ibov
    nome: str


class IndicadorSeriePonto(BaseModel):
    data: date
    acumulado_pct: float


class IndicadorSerie(BaseModel):
    codigo: str
    pontos: list[IndicadorSeriePonto]
