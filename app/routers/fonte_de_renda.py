"""Endpoints CRUD de `fonte_de_renda` (entidade do usuário)."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.usuario import Usuario
from app.repositories.fonte_de_renda import FonteDeRendaRepository
from app.schemas.fonte_de_renda import (
    FonteDeRendaCreate,
    FonteDeRendaRead,
    FonteDeRendaUpdate,
)
from app.security.current_user import get_current_user

router = APIRouter(prefix="/fontes-de-renda", tags=["fonte_de_renda"])


def _repo(
    db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)
) -> FonteDeRendaRepository:
    return FonteDeRendaRepository(db, user.id)


@router.get("", response_model=list[FonteDeRendaRead])
def listar(repo: FonteDeRendaRepository = Depends(_repo)) -> list[FonteDeRendaRead]:
    return repo.list()


@router.post("", response_model=FonteDeRendaRead, status_code=status.HTTP_201_CREATED)
def criar(
    payload: FonteDeRendaCreate, repo: FonteDeRendaRepository = Depends(_repo)
) -> FonteDeRendaRead:
    return repo.create(**payload.model_dump())


@router.get("/{fonte_id}", response_model=FonteDeRendaRead)
def obter(fonte_id: int, repo: FonteDeRendaRepository = Depends(_repo)) -> FonteDeRendaRead:
    fonte = repo.get(fonte_id)
    if fonte is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "fonte de renda não encontrada")
    return fonte


@router.patch("/{fonte_id}", response_model=FonteDeRendaRead)
def atualizar(
    fonte_id: int,
    payload: FonteDeRendaUpdate,
    repo: FonteDeRendaRepository = Depends(_repo),
) -> FonteDeRendaRead:
    fonte = repo.get(fonte_id)
    if fonte is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "fonte de renda não encontrada")
    return repo.update(fonte, **payload.model_dump(exclude_unset=True))


@router.delete("/{fonte_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover(fonte_id: int, repo: FonteDeRendaRepository = Depends(_repo)) -> None:
    fonte = repo.get(fonte_id)
    if fonte is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "fonte de renda não encontrada")
    repo.delete(fonte)
