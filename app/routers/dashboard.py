"""Router do dashboard (§4.10). Período padrão = mês corrente (fuso SP)."""

from dataclasses import dataclass
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.transacao import Transacao
from app.models.usuario import Usuario
from app.routers.transacao import ler_itens
from app.schemas.dashboard import (
    AnaliseNatureza,
    CartoesResumo,
    DashboardResumo,
    DashboardSeries,
    PatrimonioSerie,
)
from app.schemas.transacao import TransacaoListagem
from app.security.current_user import get_current_user
from app.services.dashboard import (
    FiltroLancamentos,
    lancamentos_da_analise,
    montar_analise,
    montar_cartoes,
    montar_dashboard,
    montar_patrimonio,
    montar_series,
)
from app.services.gasto_usuario import VISAO_PADRAO, Visao
from app.services.periodo import mes_corrente
from app.services.revisao import corte_revisao

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardResumo)
def obter(
    inicio: date | None = Query(None),
    fim: date | None = Query(None),
    visao: Visao = Query(VISAO_PADRAO),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
) -> DashboardResumo:
    if inicio is None or fim is None:
        inicio, fim = mes_corrente()
    return montar_dashboard(db, user.id, inicio, fim, corte_revisao(user.revisao_desde), visao)


@router.get("/series", response_model=DashboardSeries)
def series(
    inicio: date | None = Query(None),
    fim: date | None = Query(None),
    granularidade: Literal["diaria", "semanal", "mensal", "anual"] = Query("semanal"),
    visao: Visao = Query(VISAO_PADRAO),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
) -> DashboardSeries:
    if inicio is None or fim is None:
        inicio, fim = mes_corrente()
    return montar_series(db, user.id, inicio, fim, granularidade, visao)


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


Natureza = Literal["receita", "despesa"]
# ponytail: teto do drill-down (mesmo da listagem); o diálogo avisa "N de T" quando corta.
_LIMITE_DRILLDOWN = 200


def _periodo(inicio: date | None, fim: date | None) -> tuple[date, date]:
    if inicio is None or fim is None:
        return mes_corrente()
    if fim < inicio:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "fim antes de inicio")
    if (fim - inicio).days > 3 * 366:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "período maior que 3 anos")
    return inicio, fim


@router.get("/analise", response_model=AnaliseNatureza)
def analise(
    natureza: Natureza = Query(),
    inicio: date | None = Query(None),
    fim: date | None = Query(None),
    visao: Visao = Query(VISAO_PADRAO),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
) -> AnaliseNatureza:
    """Abas Receitas/Despesas: totais vs período anterior, categorias, maiores contrapartes, meios
    de pagamento, dia da semana, acumulado diário e orçamento (previsto) × realizado."""
    return montar_analise(db, user.id, natureza, *_periodo(inicio, fim), visao)


@dataclass
class _FiltroQuery:
    """Filtros do drill-down (query string) — agrupados para a assinatura da rota ficar enxuta."""

    categoria_id: str | None = Query(None, min_length=1, max_length=16)
    contraparte: str | None = Query(None, max_length=200)  # = `_MAX_CHAVE` do produtor
    meio: str | None = Query(None, max_length=64)
    conta_id: int | None = Query(None)


@router.get("/analise/transacoes", response_model=TransacaoListagem)
def analise_transacoes(
    natureza: Natureza = Query(),
    inicio: date | None = Query(None),
    fim: date | None = Query(None),
    f: _FiltroQuery = Depends(),
    visao: Visao = Query(VISAO_PADRAO),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
) -> TransacaoListagem:
    """Transações de um pedaço da análise (categoria, contraparte, meio e/ou conta). Mesmo recorte
    dos gráficos: a soma bate com o valor exibido. Até 200, mais recentes primeiro."""
    filtro = FiltroLancamentos(f.categoria_id, f.contraparte, f.meio, f.conta_id)
    lancs = lancamentos_da_analise(db, user.id, natureza, _periodo(inicio, fim), filtro, visao)
    pagina = lancs[:_LIMITE_DRILLDOWN]
    ids = [x.transacao_id for x in pagina if x.transacao_id is not None]
    txs = {
        t.id: t
        for t in db.scalars(
            select(Transacao).where(Transacao.usuario_id == user.id, Transacao.id.in_(ids))
        )
    }
    itens = [txs[x.transacao_id] if x.transacao_id is not None else x.divisao_id for x in pagina]
    return TransacaoListagem(
        items=ler_itens(db, user.id, itens, corte_revisao(user.revisao_desde)), total=len(lancs)
    )
