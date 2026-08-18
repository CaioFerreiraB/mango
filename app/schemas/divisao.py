"""Schemas de `divisao_despesa` (§4.11). `criado_por` vem do usuário atual (não no payload).

`DivisaoDespesaRead` é enriquecido em runtime (participantes + meu saldo), não é um `read_model`
puro — mesmo padrão de `ObjetivoRead`/`ObjetivoDetalheRead` (app/schemas/objetivo.py).
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas import ORMModel

ModoDivisao = Literal["igualmente", "integral"]
EscopoDivisao = Literal["todas", "minhas", "comigo", "arquivadas"]
StatusPessoa = Literal["usuario", "so_divisao"]


class DivisaoDespesaCreate(BaseModel):
    descricao: str | None = None
    categoria_id: str | None = Field(default=None, max_length=16)
    valor_total_centavos: int = Field(gt=0)
    pago_por_usuario_id: int
    modo_divisao: ModoDivisao
    # Ids dos usuários que dividem a despesa. No modo `igualmente` inclui quem pagou; no modo
    # `integral` tem exatamente 1 id (o devedor, diferente de quem pagou) — validado no service.
    participantes: list[int] = Field(min_length=1)


class DivisaoDespesaUpdate(BaseModel):
    descricao: str | None = None
    categoria_id: str | None = Field(default=None, max_length=16)
    valor_total_centavos: int | None = Field(default=None, gt=0)
    pago_por_usuario_id: int | None = None
    modo_divisao: ModoDivisao | None = None
    participantes: list[int] | None = Field(default=None, min_length=1)


class DivisaoParticipanteRead(BaseModel):
    usuario_id: int
    nome: str
    avatar: int | None
    valor_centavos: int


class DivisaoDespesaRead(ORMModel):
    id: int
    criado_por_usuario_id: int
    pago_por_usuario_id: int
    descricao: str | None
    categoria_id: str | None
    valor_total_centavos: int
    modo_divisao: str
    quitada: bool
    arquivada: bool
    criado_em: datetime
    atualizado_em: datetime
    # Calculados: linhas de participantes e o saldo do usuário atual nesta despesa
    # (positivo = me devem, negativo = eu devo).
    participantes: list[DivisaoParticipanteRead] = []
    meu_saldo_centavos: int = 0


class ResumoDivisoes(BaseModel):
    saldo_a_receber_centavos: int
    pessoas_a_receber: int
    saldo_a_pagar_centavos: int
    pessoas_a_pagar: int
    saldo_total_centavos: int


class PessoaDivisao(BaseModel):
    usuario_id: int
    nome: str
    avatar: int | None
    status: StatusPessoa
    saldo_centavos: int
    ultima_atividade: datetime | None
