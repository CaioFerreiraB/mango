"""Router de `item_pluggy` — valida que a credencial referenciada é do próprio usuário.

Inclui o vínculo manual de instituição (vale para todas as contas da conexão) — ver
`app/services/item.py`.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.usuario import Usuario
from app.repositories.pluggy import CredencialPluggyRepository, ItemPluggyRepository
from app.schemas.pluggy import (
    ItemInstituicaoUpdate,
    ItemPluggyCreate,
    ItemPluggyRead,
    ItemPluggyUpdate,
)
from app.security.current_user import get_current_user
from app.services import item as item_service

router = APIRouter(prefix="/itens-pluggy", tags=["item_pluggy"])


def _repo(
    db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)
) -> ItemPluggyRepository:
    return ItemPluggyRepository(db, user.id)


@router.get("", response_model=list[ItemPluggyRead])
def listar(repo: ItemPluggyRepository = Depends(_repo)):
    return repo.list()


@router.post("", response_model=ItemPluggyRead, status_code=status.HTTP_201_CREATED)
def criar(
    payload: ItemPluggyCreate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    # A credencial precisa existir e ser do próprio usuário (isolamento, §5.2).
    if CredencialPluggyRepository(db, user.id).get(payload.credencial_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "credencial não encontrada")
    return ItemPluggyRepository(db, user.id).create(**payload.model_dump())


@router.get("/{item_id}", response_model=ItemPluggyRead)
def obter(item_id: int, repo: ItemPluggyRepository = Depends(_repo)):
    item = repo.get(item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "item não encontrado")
    return item


@router.patch("/{item_id}", response_model=ItemPluggyRead)
def atualizar(item_id: int, payload: ItemPluggyUpdate, repo: ItemPluggyRepository = Depends(_repo)):
    item = repo.get(item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "item não encontrado")
    return repo.update(item, **payload.model_dump(exclude_unset=True))


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover(item_id: int, repo: ItemPluggyRepository = Depends(_repo)):
    item = repo.get(item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "item não encontrado")
    repo.delete(item)


@router.put("/{item_id}/instituicao", response_model=ItemPluggyRead)
def vincular_instituicao(
    item_id: int,
    payload: ItemInstituicaoUpdate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
) -> ItemPluggyRead:
    return item_service.vincular_instituicao(
        db, user.id, item_id, payload.pluggy_connector_id, payload.nome, payload.logo_url
    )
