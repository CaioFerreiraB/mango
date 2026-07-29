"""Router do dashboard (§4.10). Período padrão = mês corrente (fuso SP)."""

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.usuario import Usuario
from app.schemas.dashboard import DashboardResumo, DashboardSeries
from app.security.current_user import get_current_user
from app.services.dashboard import montar_dashboard, montar_series
from app.services.periodo import mes_corrente

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
    return montar_dashboard(db, user.id, inicio, fim)


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
