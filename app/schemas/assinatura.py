"""Schemas de `assinatura` (§4.7)."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.assinatura import Assinatura
from app.schemas.auto import read_model

AssinaturaRead = read_model(Assinatura, overrides={"nomes_transacao": list[str]})

Periodicidade = Literal["mensal", "trimestral", "semestral", "anual", "irregular"]


class AssinaturaCreate(BaseModel):
    nome: str = Field(min_length=1, max_length=255)
    descricao: str | None = None
    valor_centavos: int = Field(ge=0)
    categoria_id: str | None = Field(default=None, max_length=16)
    periodicidade: Periodicidade
    data_inicio: date | None = None
    ativa: bool = True
    detectada_automaticamente: bool = False
    conta_id: int | None = None
    # Nomes de transação (aliases) para casar cobranças no sync/dedup.
    nomes_transacao: list[str] = Field(default_factory=list)


class AssinaturaUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=255)
    descricao: str | None = None
    valor_centavos: int | None = Field(default=None, ge=0)
    categoria_id: str | None = Field(default=None, max_length=16)
    periodicidade: Periodicidade | None = None
    data_inicio: date | None = None
    ativa: bool | None = None
    nomes_transacao: list[str] | None = None


class AssinaturaCandidatoRead(BaseModel):
    """Assinatura candidata detectada nas transações, ainda não persistida (§4.7). Serializa o
    dataclass `Candidato` da heurística (`from_attributes`)."""

    model_config = ConfigDict(from_attributes=True)

    nome: str
    valor_centavos: int  # mediana em reais (valor efetivo na conta)
    moeda: str  # currency_code predominante
    valor_moeda_centavos: int | None  # mediana na moeda estrangeira, só quando moeda != BRL
    periodicidade: Periodicidade
    categoria_id: str | None
    conta_id: int | None
    data_inicio: date
    ocorrencias: int
    transacao_ids: list[int]  # ids das transações do grupo (p/ marcar "não é assinatura")


class AssinaturaCategoriaTotal(BaseModel):
    categoria_id: str | None
    total_mensal_centavos: int


class AssinaturaResumoRead(BaseModel):
    """Visões do §4.7: total mensal-equivalente, total por categoria e lista de vigentes."""

    total_mensal_centavos: int
    por_categoria: list[AssinaturaCategoriaTotal]
    vigentes: list[AssinaturaRead]
