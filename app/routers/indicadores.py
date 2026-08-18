"""Indicadores de mercado (§4.9): lista disponível + séries normalizadas p/ comparação.

Requer usuário autenticado (mesmo sendo dado público, não expomos proxy aberto). Erros da
fonte viram 502 com mensagem genérica; o detalhe redigido vai ao log (padrão do sync)."""

import logging
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.exceptions import UpstreamError
from app.models.usuario import Usuario
from app.schemas.indicadores import IndicadorInfo, IndicadorSerie, IndicadorSeriePonto
from app.security.current_user import get_current_user
from app.services import indicadores
from app.services.brapi import token_brapi
from app.services.indicadores import IndicadorError

router = APIRouter(prefix="/indicadores", tags=["indicadores"])
logger = logging.getLogger("app.indicadores")

_MAX_JANELA_DIAS = 3700
_CODIGOS_VALIDOS = ("cdi", "selic", "ipca", "ibov")


@router.get("", response_model=list[IndicadorInfo])
def listar(
    db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)
) -> list[IndicadorInfo]:
    return [IndicadorInfo(**i) for i in indicadores.disponiveis(token_brapi(db, user.id))]


@router.get("/serie", response_model=list[IndicadorSerie])
def series(
    codigos: str = Query(description="códigos separados por vírgula, ex.: cdi,ipca"),
    inicio: date = Query(),
    fim: date = Query(),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
) -> list[IndicadorSerie]:
    if inicio > fim or (fim - inicio) > timedelta(days=_MAX_JANELA_DIAS):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "período inválido")
    pedidos = [c.strip().lower() for c in codigos.split(",") if c.strip()]
    if not pedidos or any(c not in _CODIGOS_VALIDOS for c in pedidos):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "indicador desconhecido")
    tok = token_brapi(db, user.id)
    out: list[IndicadorSerie] = []
    falhas = 0
    for codigo in dict.fromkeys(pedidos):  # dedup preservando ordem
        try:
            pontos = indicadores.serie(codigo, inicio, fim, tok)
        except IndicadorError as exc:
            # Um indicador indisponível (IBOV sem plano brapi p/ janela longa, timeout transitório
            # do BCB, …) não pode derrubar os demais: pula e segue com os que responderam. Só vira
            # 502 quando TODOS falham (aí é indisponibilidade real da fonte, retentável).
            logger.warning("indicador %s falhou: %s", codigo, exc)
            falhas += 1
            continue
        out.append(
            IndicadorSerie(
                codigo=codigo,
                pontos=[IndicadorSeriePonto(data=d, acumulado_pct=p) for d, p in pontos],
            )
        )
    if falhas and not out:
        raise UpstreamError("não foi possível buscar os indicadores agora")
    return out
