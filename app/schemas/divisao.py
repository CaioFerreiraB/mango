"""Schemas de `divisao_despesa` (§4.11). `criado_por` vem do usuário atual (não no payload).

`DivisaoDespesaRead` é enriquecido em runtime (participantes + meu saldo), não é um `read_model`
puro — mesmo padrão de `ObjetivoRead`/`ObjetivoDetalheRead` (app/schemas/objetivo.py).
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas import ORMModel

ModoDivisao = Literal["igualmente", "integral", "porcentagem", "valor"]
# `sem_transacao`: pagas por mim ainda sem transação vinculada (picker "divisão existente").
EscopoDivisao = Literal["todas", "minhas", "comigo", "arquivadas", "sem_transacao"]
StatusPessoa = Literal["usuario", "so_divisao"]


class ParteDivisao(BaseModel):
    """Fatia de uma pessoa nos modos `porcentagem` (centésimos de ponto percentual: 2500 = 25%,
    somando 10000) e `valor` (centavos, somando o total). Inclui quem pagou, se ele tem parte."""

    usuario_id: int
    valor: int = Field(ge=0)


class DivisaoDespesaCreate(BaseModel):
    descricao: str | None = None
    categoria_id: str | None = Field(default=None, max_length=16)
    valor_total_centavos: int = Field(gt=0)
    pago_por_usuario_id: int
    modo_divisao: ModoDivisao
    # Ids dos usuários que dividem a despesa (`igualmente`/`integral`). No modo `igualmente` inclui
    # quem pagou; no modo `integral` tem exatamente 1 id (o devedor, diferente de quem pagou).
    participantes: list[int] = []
    # Fatias de cada pessoa (`porcentagem`/`valor`) — validado no service.
    partes: list[ParteDivisao] | None = None
    # Quando aconteceu (padrão: agora). Com `transacao_id`, vale a data da transação.
    data: datetime | None = None
    # Transação do pagador que corresponde à despesa (só quando quem cria é quem pagou).
    transacao_id: int | None = Field(default=None, gt=0)
    sem_transacao: bool = False
    # Transação com valor diferente do total: True recalcula a divisão para o valor dela; False
    # mantém a divisão e o orçamento conta a transação menos a parte dos outros.
    reajustar: bool = False


class DivisaoVinculo(BaseModel):
    """Vínculo da divisão com a transação do pagador. `transacao_id` vincula; os dois vazios
    desvinculam (volta a pendente); `sem_transacao` = "paguei fora do banco". `reajustar`: ver
    `DivisaoDespesaCreate`."""

    transacao_id: int | None = Field(default=None, gt=0)
    sem_transacao: bool = False
    reajustar: bool = False


class DivisaoDespesaUpdate(BaseModel):
    descricao: str | None = None
    categoria_id: str | None = Field(default=None, max_length=16)
    valor_total_centavos: int | None = Field(default=None, gt=0)
    pago_por_usuario_id: int | None = None
    modo_divisao: ModoDivisao | None = None
    participantes: list[int] | None = Field(default=None, min_length=1)
    partes: list[ParteDivisao] | None = None
    data: datetime | None = None


class DivisaoParticipanteRead(BaseModel):
    usuario_id: int
    nome: str
    avatar: int | None
    valor_centavos: int
    percentual_bp: int | None = None


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
    data: datetime
    transacao_id: int | None
    sem_transacao: bool
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
