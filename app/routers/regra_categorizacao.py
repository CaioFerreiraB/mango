"""Router de `regra_categorizacao` (§4.5).

Manual, e não via `make_crud_router`, porque toda mutação precisa reaplicar as regras às
transações — a factory só tem gancho de update.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.usuario import Usuario
from app.schemas.regra_categorizacao import (
    RegraCategorizacaoCreate,
    RegraCategorizacaoRead,
    RegraCategorizacaoUpdate,
)
from app.security.current_user import get_current_user
from app.services import regra_categorizacao as regra_service

router = APIRouter(prefix="/regras-categorizacao", tags=["regra_categorizacao"])


@router.get("", response_model=list[RegraCategorizacaoRead])
def listar(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    return regra_service.listar(db, user.id)


@router.post("", response_model=RegraCategorizacaoRead, status_code=status.HTTP_201_CREATED)
def criar(
    payload: RegraCategorizacaoCreate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return regra_service.criar(
        db,
        user.id,
        texto=payload.texto,
        tipo_match=payload.tipo_match,
        categoria_id=payload.categoria_id,
    )


@router.get("/{regra_id}", response_model=RegraCategorizacaoRead)
def obter(regra_id: int, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    return regra_service.obter(db, user.id, regra_id)


@router.patch("/{regra_id}", response_model=RegraCategorizacaoRead)
def atualizar(
    regra_id: int,
    payload: RegraCategorizacaoUpdate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return regra_service.atualizar(
        db,
        user.id,
        regra_id,
        texto=payload.texto,
        tipo_match=payload.tipo_match,
        categoria_id=payload.categoria_id,
    )


@router.delete("/{regra_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover(
    regra_id: int, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)
):
    regra_service.remover(db, user.id, regra_id)
