"""Schemas de orçamento (§4.6, #20). A regra soma-subcat ≤ cat é validada no service."""

from pydantic import BaseModel, Field

from app.models.orcamento import Orcamento, OrcamentoMensal
from app.schemas.auto import read_model

OrcamentoRead = read_model(Orcamento)
OrcamentoMensalRead = read_model(OrcamentoMensal)


class OrcamentoCreate(BaseModel):
    categoria_id: str = Field(min_length=1, max_length=16)
    limite_padrao_centavos: int = Field(ge=0)
    recorrente: bool = True
    ativo: bool = True


class OrcamentoUpdate(BaseModel):
    limite_padrao_centavos: int | None = Field(default=None, ge=0)
    recorrente: bool | None = None
    ativo: bool | None = None


class OrcamentoMensalCreate(BaseModel):
    orcamento_id: int
    categoria_id: str = Field(min_length=1, max_length=16)
    ano: int = Field(ge=2000, le=2100)
    mes: int = Field(ge=1, le=12)
    limite_centavos: int = Field(ge=0)
    editado_manualmente: bool = False


class OrcamentoMensalUpdate(BaseModel):
    limite_centavos: int | None = Field(default=None, ge=0)
    editado_manualmente: bool | None = None


class OrcamentoConsumoItem(BaseModel):
    """Consumo de um orçamento no mês. `alerta_atingido` é o maior limiar cruzado (§4.6)."""

    orcamento_id: int
    orcamento_mensal_id: int  # linha do mês (editar o limite via PATCH /orcamentos-mensais/{id})
    categoria_id: str
    limite_centavos: int
    gasto_centavos: int
    percentual: int
    alerta_atingido: int | None  # 50 | 75 | 90 | 100, ou None se abaixo de 50%


class OrcamentoConsumoRead(BaseModel):
    ano: int
    mes: int
    itens: list[OrcamentoConsumoItem]
