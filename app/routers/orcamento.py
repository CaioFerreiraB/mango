"""Router de orçamento — CRUD com a regra #20 (no service). `orcamento_mensal` é CRUD puro."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.usuario import Usuario
from app.repositories.orcamento import OrcamentoRepository
from app.schemas.orcamento import (
    OrcamentoConsumoRead,
    OrcamentoCreate,
    OrcamentoRead,
    OrcamentoUpdate,
)
from app.security.current_user import get_current_user
from app.services import orcamento as orcamento_service
from app.services import orcamento_consumo
from app.services.orcamento_mensal import materializar_mes

router = APIRouter(prefix="/orcamentos", tags=["orcamento"])


def _repo(
    db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)
) -> OrcamentoRepository:
    return OrcamentoRepository(db, user.id)


@router.get("", response_model=list[OrcamentoRead])
def listar(repo: OrcamentoRepository = Depends(_repo)):
    return repo.list()


@router.post("", response_model=OrcamentoRead, status_code=status.HTTP_201_CREATED)
def criar(
    payload: OrcamentoCreate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return orcamento_service.criar(db, user.id, payload.model_dump())


# Declarado antes de `/{orcamento_id}` para a rota estática não ser capturada pelo path param.
@router.get("/consumo", response_model=OrcamentoConsumoRead)
def consumo(
    ano: int = Query(ge=2000, le=2100),
    mes: int = Query(ge=1, le=12),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Consumo e alertas (50/75/90/100%) dos orçamentos do mês (§4.6)."""
    return orcamento_consumo.consumo_do_mes(db, user.id, ano, mes)


# Declarado antes de `/{orcamento_id}` pelo mesmo motivo de `/consumo`.
@router.post("/materializar", response_model=OrcamentoConsumoRead)
def materializar(
    ano: int = Query(ge=2000, le=2100),
    mes: int = Query(ge=1, le=12),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Aplica o orçamento padrão a um mês específico, sob pedido do usuário — normalmente pra
    um mês passado sem nada configurado (a materialização automática só cobre o mês corrente,
    §4.6). Idempotente: não sobrescreve linhas que já existem."""
    materializar_mes(db, user.id, ano, mes)
    return orcamento_consumo.consumo_do_mes(db, user.id, ano, mes)


@router.get("/{orcamento_id}", response_model=OrcamentoRead)
def obter(orcamento_id: int, repo: OrcamentoRepository = Depends(_repo)):
    orc = repo.get(orcamento_id)
    if orc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "orçamento não encontrado")
    return orc


@router.patch("/{orcamento_id}", response_model=OrcamentoRead)
def atualizar(
    orcamento_id: int,
    payload: OrcamentoUpdate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return orcamento_service.atualizar(
        db, user.id, orcamento_id, payload.model_dump(exclude_unset=True)
    )


@router.delete("/{orcamento_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover(orcamento_id: int, repo: OrcamentoRepository = Depends(_repo)):
    orc = repo.get(orcamento_id)
    if orc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "orçamento não encontrado")
    repo.delete(orc)
