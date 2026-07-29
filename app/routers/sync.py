"""Sincronização com o Pluggy (§4.3): atualizar todas as conexões ou uma específica.

Mutações (POST) → passam pelo CSRF do self-hosted (S7). Erros do Pluggy viram 502 com
mensagem genérica (sem vazar corpo/segredo, S1/S7).
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.exceptions import UpstreamError
from app.models.usuario import Usuario
from app.pluggy.client import PluggyError
from app.schemas.sync import ResumoSyncRead
from app.security.current_user import get_current_user
from app.services.sync import sincronizar_usuario

router = APIRouter(tags=["sync"])
logger = logging.getLogger("app.sync")


def _sincronizar(db: Session, usuario_id: int, item_id: int | None) -> ResumoSyncRead:
    try:
        resumo = sincronizar_usuario(db, usuario_id, item_id=item_id)
    except PluggyError as exc:
        # Ao cliente vai só a mensagem genérica (o detalhe do Pluggy pode conter dado interno).
        # Ao log vai o detalhe já redigido do PluggyError (só método/rota/status) p/ diagnóstico.
        logger.warning("sync falhou (usuario=%s, item=%s): %s", usuario_id, item_id, exc)
        raise UpstreamError("não foi possível falar com o Pluggy agora") from None
    return ResumoSyncRead(
        itens=resumo.itens,
        contas=resumo.contas,
        transacoes=resumo.transacoes,
        transacoes_novas=resumo.transacoes_novas,
        investimentos=resumo.investimentos,
    )


@router.post("/sync", response_model=ResumoSyncRead)
def sincronizar_tudo(
    db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)
) -> ResumoSyncRead:
    return _sincronizar(db, user.id, None)


@router.post("/itens-pluggy/{item_id}/sincronizar", response_model=ResumoSyncRead)
def sincronizar_item(
    item_id: int, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)
) -> ResumoSyncRead:
    return _sincronizar(db, user.id, item_id)
