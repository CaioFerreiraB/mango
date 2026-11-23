"""Router do dashboard (§4.10). Período padrão = mês corrente (fuso SP)."""

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.usuario import Usuario
from app.schemas.dashboard import (
    CartoesResumo,
    DashboardResumo,
    DashboardSeries,
    PatrimonioSerie,
)
from app.security.current_user import get_current_user
from app.services.dashboard import (
    montar_cartoes,
    montar_dashboard,
    montar_patrimonio,
    montar_series,
)
from app.services.periodo import mes_corrente
from app.services.revisao import corte_revisao

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardResumo)
def obter(
    inicio: date | None = Query(None),
    fim: date | None = Query(None),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
) -> DashboardResumo:
    if inicio is None or fim is None:
        inicio, fim = mes_corrente()
    return montar_dashboard(db, user.id, inicio, fim, corte_revisao(user.revisao_desde))


@router.get("/series", response_model=DashboardSeries)
def series(
    inicio: date | None = Query(None),
    fim: date | None = Query(None),
    granularidade: Literal["diaria", "semanal", "mensal"] = Query("semanal"),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
) -> DashboardSeries:
    if inicio is None or fim is None:
        inicio, fim = mes_corrente()
    return montar_series(db, user.id, inicio, fim, granularidade)


@router.get("/patrimonio", response_model=PatrimonioSerie)
def patrimonio(
    meses: int = Query(12, ge=1, le=36),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
) -> PatrimonioSerie:
    """Evolução patrimonial mês a mês (contas BANK + investimentos), terminando no mês corrente."""
    return montar_patrimonio(db, user.id, meses)


@router.get("/cartoes", response_model=CartoesResumo)
def cartoes(
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
) -> CartoesResumo:
    """Painel dos cartões: compras do mês, fatura atual, próximas, limite e resumo do ano."""
    return montar_cartoes(db, user.id)
