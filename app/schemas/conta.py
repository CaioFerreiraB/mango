"""Schemas de `conta` (Pluggy-owned): leitura + update estreito (só `objetivo_id`)."""

from datetime import date, datetime

from pydantic import BaseModel

from app.models.cartao_fatura import Cartao, ContaBancaria, ContaSaldoReservado
from app.schemas import ORMModel
from app.schemas.auto import read_model

ContaBancariaRead = read_model(ContaBancaria)
CartaoRead = read_model(Cartao)
ContaSaldoReservadoRead = read_model(ContaSaldoReservado)


class ContaRead(ORMModel):
    id: int
    usuario_id: int
    item_id: int
    instituicao_id: int
    pluggy_account_id: str
    type: str
    subtype: str | None
    nome: str | None
    marketing_name: str | None
    numero: str | None
    owner: str | None
    tax_number: str | None
    saldo_centavos: int
    currency_code: str
    objetivo_id: int | None
    instituicao_manual_id: int | None
    # Do cartão 1:1 (só CREDIT) — necessários para a arte do cartão na listagem (bandeira + tipo).
    brand: str | None = None
    level: str | None = None
    pluggy_criado_em: datetime | None
    pluggy_atualizado_em: datetime | None


class ContaDetalheRead(ContaRead):
    """Detalhe da conta com as tabelas 1:1 embutidas (§4.2). Montado no router."""

    conta_bancaria: ContaBancariaRead | None = None
    cartao: CartaoRead | None = None
    saldos_reservados: list[ContaSaldoReservadoRead] = []


class SaldoDiarioPonto(ORMModel):
    data: date
    saldo_centavos: int


class ContaSaldoSerie(BaseModel):
    """Série de saldo diário (fecho de cada dia) de uma conta BANK, para o sparkline dos cards."""

    conta_id: int
    pontos: list[SaldoDiarioPonto]


class ContaUpdate(BaseModel):
    """Update estreito (§4 crud.md): o usuário só altera o vínculo com objetivo.

    `objetivo_id=None` desvincula. Campos importados do Pluggy não são editáveis aqui.
    """

    objetivo_id: int | None = None


class ContaInstituicaoUpdate(BaseModel):
    """Vínculo manual da conta a uma instituição escolhida no catálogo do Pluggy.

    `pluggy_connector_id=None` remove o vínculo. Com connector, `nome` é obrigatório e
    `logo_url` é o `imageUrl` do connector (opcional).
    """

    pluggy_connector_id: int | None = None
    nome: str | None = None
    logo_url: str | None = None
