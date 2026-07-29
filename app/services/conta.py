"""Regras de `conta`. Writes do usuário: vincular a um objetivo (§4.8) e à instituição manual.

Valida que o objetivo é do MESMO usuário (isolamento) antes de vincular.
"""

from sqlalchemy.orm import Session

from app.exceptions import NotFoundError
from app.models.conta import Conta
from app.pluggy.catalogo import CATALOGO_BR
from app.repositories.conta import ContaRepository
from app.repositories.objetivo import ObjetivoRepository
from app.repositories.pluggy import InstituicaoRepository
from app.schemas.pluggy import ConnectorRead


def vincular_objetivo(
    db: Session, usuario_id: int, conta_id: int, objetivo_id: int | None
) -> Conta:
    contas = ContaRepository(db, usuario_id)
    conta = contas.get(conta_id)
    if conta is None:
        raise NotFoundError("conta não encontrada")

    if objetivo_id is not None:
        # Garante que o objetivo existe e pertence ao usuário (nunca de outro #4/§5.2).
        if ObjetivoRepository(db, usuario_id).get(objetivo_id) is None:
            raise NotFoundError("objetivo não encontrado")

    return contas.update(conta, objetivo_id=objetivo_id)


def vincular_instituicao(
    db: Session,
    usuario_id: int,
    conta_id: int,
    pluggy_connector_id: int | None,
    nome: str | None,
    logo_url: str | None,
) -> Conta:
    """Aponta a conta a uma instituição manual (do catálogo do Pluggy). `pluggy_connector_id=None`
    remove o vínculo. NÃO toca `instituicao_id` (a original do sync fica intacta)."""
    contas = ContaRepository(db, usuario_id)
    conta = contas.get(conta_id)
    if conta is None:
        raise NotFoundError("conta não encontrada")

    if pluggy_connector_id is None:
        return contas.update(conta, instituicao_manual_id=None)

    if not nome:
        raise NotFoundError("nome da instituição é obrigatório")
    inst = InstituicaoRepository(db, usuario_id).upsert_by_connector(
        pluggy_connector_id, nome=nome, logo_url=logo_url
    )
    return contas.update(conta, instituicao_manual_id=inst.id)


def listar_connectores(nome: str | None = None) -> list[ConnectorRead]:
    """Catálogo curado de instituições para o seletor de vínculo manual (`app/pluggy/catalogo.py`).

    Estático: as credenciais sandbox do Pluggy não expõem o catálogo real. `nome` filtra por busca
    parcial (o front também filtra client-side).
    """
    itens = [
        ConnectorRead(pluggy_connector_id=cid, nome=n, logo_url=logo)
        for cid, n, logo in CATALOGO_BR
    ]
    if nome:
        q = nome.lower()
        itens = [c for c in itens if q in c.nome.lower()]
    return itens
