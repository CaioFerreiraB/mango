"""Schemas de `divisao_despesa` (§4.11). `criado_por` vem do usuário atual (não no payload)."""

from typing import Literal

from pydantic import BaseModel, Field

from app.models.divisao import DivisaoDespesa
from app.schemas.auto import read_model

DivisaoDespesaRead = read_model(DivisaoDespesa)

ModoDivisao = Literal[
    "pago_mim_dividir", "pago_mim_recebo", "pago_outro_dividir", "pago_outro_recebo"
]


class DivisaoDespesaCreate(BaseModel):
    outro_usuario_id: int
    valor_centavos: int = Field(ge=0)
    descricao: str | None = None
    categoria_id: str | None = Field(default=None, max_length=8)
    modo_divisao: ModoDivisao
    quitada: bool = False


class DivisaoDespesaUpdate(BaseModel):
    valor_centavos: int | None = Field(default=None, ge=0)
    descricao: str | None = None
    categoria_id: str | None = Field(default=None, max_length=8)
    modo_divisao: ModoDivisao | None = None
    quitada: bool | None = None
