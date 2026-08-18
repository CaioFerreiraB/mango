"""Regras de `item_pluggy` (conexão). Write do usuário: vincular a instituição manual (catálogo
do Pluggy) — vale para TODAS as contas do item, não por conta individual.
"""

from sqlalchemy.orm import Session

from app.exceptions import NotFoundError
from app.models.pluggy import ItemPluggy
from app.pluggy.catalogo import CATALOGO_BR
from app.repositories.pluggy import InstituicaoRepository, ItemPluggyRepository
from app.schemas.pluggy import ConnectorRead


def vincular_instituicao(
    db: Session,
    usuario_id: int,
    item_id: int,
    pluggy_connector_id: int | None,
    nome: str | None,
    logo_url: str | None,
) -> ItemPluggy:
    """Aponta a conexão a uma instituição manual (do catálogo do Pluggy). Vale para todas as
    contas desse item. `pluggy_connector_id=None` remove o vínculo."""
    itens = ItemPluggyRepository(db, usuario_id)
    item = itens.get(item_id)
    if item is None:
        raise NotFoundError("conexão não encontrada")

    if pluggy_connector_id is None:
        return itens.update(item, instituicao_manual_id=None)

    if not nome:
        raise NotFoundError("nome da instituição é obrigatório")
    inst = InstituicaoRepository(db, usuario_id).upsert_by_connector(
        pluggy_connector_id, nome=nome, logo_url=logo_url
    )
    return itens.update(item, instituicao_manual_id=inst.id)


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
