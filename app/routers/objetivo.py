"""Router de `objetivo` (§4.8): CRUD do usuário + leitura enriquecida (valor guardado,
progresso, vínculos). O vínculo em si é gravado pelo lado da conta/investimento (PATCH
`objetivo_id`) — ver `app/routers/conta.py` e `app/routers/investimento.py`."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.usuario import Usuario
from app.repositories.objetivo import ObjetivoRepository
from app.schemas.objetivo import (
    ObjetivoCreate,
    ObjetivoDetalheRead,
    ObjetivoRead,
    ObjetivoUpdate,
)
from app.security.current_user import get_current_user
from app.services import objetivo as objetivo_service

router = APIRouter(prefix="/objetivos", tags=["objetivo"])


def _repo(
    db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)
) -> ObjetivoRepository:
    return ObjetivoRepository(db, user.id)


@router.get("", response_model=list[ObjetivoRead])
def listar(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    return objetivo_service.listar(db, user.id)


@router.post("", response_model=ObjetivoRead, status_code=status.HTTP_201_CREATED)
def criar(payload: ObjetivoCreate, repo: ObjetivoRepository = Depends(_repo)):
    obj = repo.create(**payload.model_dump())
    return objetivo_service.enriquecer_um(repo.db, repo.usuario_id, obj)


@router.get("/{objetivo_id}", response_model=ObjetivoDetalheRead)
def obter(
    objetivo_id: int, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)
):
    detalhe = objetivo_service.obter(db, user.id, objetivo_id)
    if detalhe is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "objetivo não encontrado")
    return detalhe


@router.patch("/{objetivo_id}", response_model=ObjetivoRead)
def atualizar(objetivo_id: int, payload: ObjetivoUpdate, repo: ObjetivoRepository = Depends(_repo)):
    obj = repo.get(objetivo_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "objetivo não encontrado")
    obj = repo.update(obj, **payload.model_dump(exclude_unset=True))
    return objetivo_service.enriquecer_um(repo.db, repo.usuario_id, obj)


@router.delete("/{objetivo_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover(objetivo_id: int, repo: ObjetivoRepository = Depends(_repo)):
    obj = repo.get(objetivo_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "objetivo não encontrado")
    repo.delete(obj)
