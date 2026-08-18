"""Router de `divisao_despesa` (§4.11): visibilidade multi-usuário, sem CRUD genérico (a lógica
de rateio/saldo mora em `app/services/divisao.py`). Rotas estáticas (`/resumo`, `/pessoas`, ...)
vêm antes de `/{despesa_id}`, mesmo cuidado de `app/routers/orcamento.py`.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.usuario import Usuario
from app.schemas.divisao import (
    DivisaoDespesaCreate,
    DivisaoDespesaRead,
    DivisaoDespesaUpdate,
    EscopoDivisao,
    PessoaDivisao,
    ResumoDivisoes,
)
from app.security.current_user import get_current_user
from app.services import divisao as divisao_service

router = APIRouter(prefix="/divisoes-despesa", tags=["divisao_despesa"])


@router.get("", response_model=list[DivisaoDespesaRead])
def listar(
    escopo: EscopoDivisao = Query(default="todas"),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return divisao_service.listar(db, user.id, escopo)


@router.post("", response_model=DivisaoDespesaRead, status_code=status.HTTP_201_CREATED)
def criar(
    payload: DivisaoDespesaCreate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return divisao_service.criar(db, user.id, payload)


# Declaradas antes de `/{despesa_id}` para as rotas estáticas não caírem no path param.
@router.get("/resumo", response_model=ResumoDivisoes)
def resumo(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    return divisao_service.resumo(db, user.id)


@router.get("/pessoas", response_model=list[PessoaDivisao])
def pessoas(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    return divisao_service.pessoas(db, user.id)


@router.get("/{despesa_id}", response_model=DivisaoDespesaRead)
def obter(
    despesa_id: int, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)
):
    despesa = divisao_service.obter(db, user.id, despesa_id)
    if despesa is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "despesa não encontrada")
    return despesa


@router.patch("/{despesa_id}", response_model=DivisaoDespesaRead)
def atualizar(
    despesa_id: int,
    payload: DivisaoDespesaUpdate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return divisao_service.atualizar(db, user.id, despesa_id, payload)


@router.delete("/{despesa_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover(
    despesa_id: int, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)
):
    divisao_service.remover(db, user.id, despesa_id)


@router.post("/{despesa_id}/quitar", response_model=DivisaoDespesaRead)
def quitar(
    despesa_id: int, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)
):
    return divisao_service.marcar_quitada(db, user.id, despesa_id, True)


@router.post("/{despesa_id}/reabrir", response_model=DivisaoDespesaRead)
def reabrir(
    despesa_id: int, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)
):
    return divisao_service.marcar_quitada(db, user.id, despesa_id, False)
