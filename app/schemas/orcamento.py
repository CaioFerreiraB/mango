"""Schemas de orçamento (§4.6, #20). A regra soma-subcat ≤ cat é validada no service."""

from typing import Literal

from pydantic import BaseModel, Field

from app.models.orcamento import Orcamento, OrcamentoMensal
from app.schemas.auto import read_model

OrcamentoRead = read_model(Orcamento)
OrcamentoMensalRead = read_model(OrcamentoMensal)

Tipo = Literal["despesa", "receita"]


class OrcamentoCreate(BaseModel):
    categoria_id: str = Field(min_length=1, max_length=16)
    tipo: Tipo
    limite_padrao_centavos: int = Field(ge=0)
    recorrente: bool = True
    ativo: bool = True
    # `ordem` não entra aqui de propósito: toda criação sempre anexa ao fim da lista do tipo
    # (o service atribui) — reordenar só existe via PATCH, depois de criado.


class OrcamentoUpdate(BaseModel):
    limite_padrao_centavos: int | None = Field(default=None, ge=0)
    recorrente: bool | None = None
    ativo: bool | None = None
    ordem: int | None = None
    # `tipo` é imutável após criado — mudar o tipo de um orçamento é, na prática, orçar outra
    # coisa (a base de cálculo do consumo muda de DEBIT pra CREDIT).


class OrcamentoMensalCreate(BaseModel):
    orcamento_id: int
    categoria_id: str = Field(min_length=1, max_length=16)
    tipo: Tipo
    ano: int = Field(ge=2000, le=2100)
    mes: int = Field(ge=1, le=12)
    limite_centavos: int = Field(ge=0)
    editado_manualmente: bool = False


class OrcamentoMensalUpdate(BaseModel):
    limite_centavos: int | None = Field(default=None, ge=0)
    editado_manualmente: bool | None = None
    # Remover/restaurar uma categoria só deste mês (sem mexer no orçamento padrão) — ver
    # `OrcamentoMensal.suprimido`.
    suprimido: bool | None = None


class OrcamentoConsumoItem(BaseModel):
    """Consumo de um orçamento no mês. `alerta_atingido` é o maior limiar cruzado (§4.6) —
    só faz sentido pra despesa (estouro de gasto); pra receita vem sempre `None`, já que
    bater/passar da meta é notícia boa, não um alerta.

    Inclui linhas `suprimido=True` (removidas só deste mês) — a Visão Geral as esconde, mas
    "Editar mês" precisa vê-las pra oferecer "restaurar" em vez de recriar do zero."""

    orcamento_id: int
    orcamento_mensal_id: int  # linha do mês (editar o limite via PATCH /orcamentos-mensais/{id})
    categoria_id: str
    tipo: Tipo
    recorrente: bool  # do orçamento padrão (True) ou pontual, só deste mês (False)
    suprimido: bool
    limite_centavos: int
    realizado_centavos: int  # despesa: gasto no período; receita: recebido no período
    percentual: int
    alerta_atingido: int | None  # 50 | 75 | 90 | 100, ou None (abaixo de 50%, ou tipo receita)


class OrcamentoConsumoRead(BaseModel):
    ano: int
    mes: int
    itens: list[OrcamentoConsumoItem]
