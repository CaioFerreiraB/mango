"""Sincronização com o Pluggy (§4.3): atualizar todas as conexões ou uma específica.

O POST só valida o escopo e dispara o sync em segundo plano (202); a UI acompanha por
`GET /sync/status` — o sync pode levar minutos e estourava o timeout do reverse proxy.
Mutações (POST) → passam pelo CSRF do self-hosted (S7). Erros do Pluggy chegam ao cliente só como
mensagem genérica no status (sem vazar corpo/segredo, S1/S7).
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.usuario import Usuario
from app.schemas.sync import ConfiguracaoSyncRead, ConfiguracaoSyncUpdate, StatusSyncRead
from app.security.current_user import get_current_user, require_admin_ou_local
from app.services import configuracao
from app.services.sync import iniciar_sync, status_sync

router = APIRouter(tags=["sync"])


@router.post("/sync", response_model=StatusSyncRead, status_code=202)
def sincronizar_tudo(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    return iniciar_sync(db, user.id)


@router.post("/itens-pluggy/{item_id}/sincronizar", response_model=StatusSyncRead, status_code=202)
def sincronizar_item(
    item_id: int, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)
):
    return iniciar_sync(db, user.id, item_id)


@router.get("/sync/status", response_model=StatusSyncRead)
def obter_status(user: Usuario = Depends(get_current_user)):
    return status_sync(user.id)


@router.get("/sync/configuracao", response_model=ConfiguracaoSyncRead)
def obter_configuracao(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    return configuracao.obter_sync(db)


@router.patch("/sync/configuracao", response_model=ConfiguracaoSyncRead)
def atualizar_configuracao(
    payload: ConfiguracaoSyncUpdate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_admin_ou_local),
):
    return configuracao.atualizar_sync(db, payload)
