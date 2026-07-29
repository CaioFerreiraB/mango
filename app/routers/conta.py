"""Endpoints de `conta` (Pluggy-owned): leitura + update estreito (vínculo a objetivo).

Sem create/delete via API — o sync do Pluggy (Fase 1) é dono dos dados importados.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.cartao_fatura import Cartao, ContaBancaria, ContaSaldoReservado
from app.models.usuario import Usuario
from app.repositories.conta import ContaRepository
from app.schemas.conta import (
    CartaoRead,
    ContaBancariaRead,
    ContaDetalheRead,
    ContaInstituicaoUpdate,
    ContaRead,
    ContaSaldoReservadoRead,
    ContaSaldoSerie,
    ContaUpdate,
)
from app.schemas.dashboard import FaturasResumo
from app.security.current_user import get_current_user
from app.services import conta as conta_service
from app.services import dashboard as dashboard_service
from app.services import saldo_diario as saldo_diario_service

router = APIRouter(prefix="/contas", tags=["conta"])


def _repo(
    db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)
) -> ContaRepository:
    return ContaRepository(db, user.id)


@router.get("", response_model=list[ContaRead])
def listar(repo: ContaRepository = Depends(_repo)) -> list[ContaRead]:
    return repo.list()


# Antes de "/{conta_id}" — senão "saldos-diarios" cairia na rota de detalhe (422 no int).
@router.get("/saldos-diarios", response_model=list[ContaSaldoSerie])
def saldos_diarios(
    dias: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
) -> list[ContaSaldoSerie]:
    return saldo_diario_service.series(db, user.id, dias)


@router.get("/{conta_id}", response_model=ContaDetalheRead)
def obter(
    conta_id: int,
    repo: ContaRepository = Depends(_repo),
    db: Session = Depends(get_db),
) -> ContaDetalheRead:
    conta = repo.get(conta_id)  # escopado por usuário → conta de outro = 404 (S3)
    if conta is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "conta não encontrada")
    # Tabelas-detalhe alcançadas pela conta (já escopada); PK = conta.id que nós geramos.
    banc = db.get(ContaBancaria, conta.id)
    cartao = db.get(Cartao, conta.id)
    reservados = (
        db.scalars(
            select(ContaSaldoReservado).where(ContaSaldoReservado.conta_bancaria_id == conta.id)
        ).all()
        if banc is not None
        else []
    )
    return ContaDetalheRead(
        **ContaRead.model_validate(conta).model_dump(),
        conta_bancaria=ContaBancariaRead.model_validate(banc) if banc else None,
        cartao=CartaoRead.model_validate(cartao) if cartao else None,
        saldos_reservados=[ContaSaldoReservadoRead.model_validate(r) for r in reservados],
    )


@router.get("/{conta_id}/faturas-resumo", response_model=FaturasResumo)
def faturas_resumo(
    conta_id: int,
    limite: int = Query(6, ge=1, le=24),
    repo: ContaRepository = Depends(_repo),
) -> FaturasResumo:
    if repo.get(conta_id) is None:  # escopo do usuário → conta de outro = 404 (S3)
        raise HTTPException(status.HTTP_404_NOT_FOUND, "conta não encontrada")
    return dashboard_service.resumo_faturas(repo.db, repo.usuario_id, conta_id, limite)


@router.patch("/{conta_id}", response_model=ContaRead)
def vincular_objetivo(
    conta_id: int,
    payload: ContaUpdate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
) -> ContaRead:
    return conta_service.vincular_objetivo(db, user.id, conta_id, payload.objetivo_id)


@router.put("/{conta_id}/instituicao", response_model=ContaRead)
def vincular_instituicao(
    conta_id: int,
    payload: ContaInstituicaoUpdate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
) -> ContaRead:
    return conta_service.vincular_instituicao(
        db, user.id, conta_id, payload.pluggy_connector_id, payload.nome, payload.logo_url
    )
