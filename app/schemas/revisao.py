from pydantic import Field

from app.schemas.assinatura import AssinaturaCreate
from app.schemas.integracao import Estrito
from app.schemas.regra_categorizacao import RegraCategorizacaoCreate
from app.schemas.transacao import TransacaoRead, TransacaoUpdate


class RevisaoPreparar(Estrito):
    transacao_id: int
    versao: str = Field(min_length=64, max_length=64)
    alteracoes: TransacaoUpdate
    assinatura: AssinaturaCreate | None = None
    regra: RegraCategorizacaoCreate | None = None


class OperacaoAplicar(Estrito):
    operacao_id: str = Field(min_length=1, max_length=64)


class RevisaoPrevia(Estrito):
    operacao_id: str
    transacoes_afetadas: int
    exige_confirmacao: bool
    efeitos: list[str]


class RevisaoItem(TransacaoRead):
    versao: str


class RevisaoFila(Estrito):
    items: list[RevisaoItem]
    total: int
    cursor: int | None
