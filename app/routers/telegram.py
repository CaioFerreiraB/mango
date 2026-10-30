"""Operações Telegram por sessão; o token MCP não alcança estas rotas."""

from urllib.parse import urlsplit, urlunsplit

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.exceptions import UpstreamError
from app.models.usuario import Usuario
from app.schemas.telegram import (
    TelegramInstanciaRead,
    TelegramInstanciaUpdate,
    TelegramRead,
    TelegramUpdate,
    VinculoConfirmar,
    VinculoRead,
)
from app.security.current_user import get_current_user, require_admin_ou_local
from app.services import telegram as service
from app.telegram_client import TelegramError

router = APIRouter(prefix="/telegram", tags=["telegram"])


def _usuario(user: Usuario = Depends(get_current_user)) -> Usuario:
    if not user.ativo:
        raise HTTPException(403, "recurso não disponível para esta conta")
    return user


def _origem_instalacao(request: Request) -> str:
    # O navegador conserva a origem pública mesmo com Vite/reverse proxy na frente da API.
    origem = request.headers.get("origin") or str(request.base_url)
    try:
        url = urlsplit(origem)
        _ = url.port
        if (
            url.scheme not in {"http", "https"}
            or not url.hostname
            or url.username
            or url.password
            or url.path not in {"", "/"}
            or url.query
            or url.fragment
            or len(origem) > 1024
            or any(c.isspace() for c in origem)
        ):
            raise ValueError
    except ValueError:
        raise HTTPException(422, "não foi possível identificar o endereço da instalação") from None
    return urlunsplit((url.scheme, url.netloc, "", "", ""))


@router.get("", response_model=TelegramRead)
def obter(db: Session = Depends(get_db), user: Usuario = Depends(_usuario)):
    with service.lock:
        return service.ler(db, user.id)


@router.patch("", response_model=TelegramRead)
def atualizar(
    payload: TelegramUpdate, db: Session = Depends(get_db), user: Usuario = Depends(_usuario)
):
    with service.lock:
        return service.preferencia(db, user.id, payload.notif_nao_revisadas)


@router.post("/vinculo", response_model=VinculoRead)
def criar_vinculo(db: Session = Depends(get_db), user: Usuario = Depends(_usuario)):
    with service.lock:
        return service.criar_vinculo(db, user.id)


@router.post("/vinculo/confirmar", response_model=TelegramRead)
def confirmar(
    payload: VinculoConfirmar, db: Session = Depends(get_db), user: Usuario = Depends(_usuario)
):
    with service.lock:
        return service.confirmar_vinculo(db, user.id, payload.solicitacao_id)


@router.delete("/vinculo", status_code=204)
def desvincular(db: Session = Depends(get_db), user: Usuario = Depends(_usuario)):
    with service.lock:
        service.desvincular(db, user.id)


@router.post("/testar", status_code=204)
def testar(db: Session = Depends(get_db), user: Usuario = Depends(_usuario)):
    with service.lock:
        service.testar(db, user.id)


@router.get("/instancia", response_model=TelegramInstanciaRead)
def obter_instancia(db: Session = Depends(get_db), user: Usuario = Depends(require_admin_ou_local)):
    with service.lock:
        return service.ler_instancia(service.instancia(db))


@router.patch("/instancia", response_model=TelegramInstanciaRead)
def atualizar_instancia(
    payload: TelegramInstanciaUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_admin_ou_local),
):
    with service.lock:
        return service.atualizar_instancia(db, payload, _origem_instalacao(request))


@router.delete("/instancia", status_code=204)
def remover_instancia(
    db: Session = Depends(get_db), user: Usuario = Depends(require_admin_ou_local)
):
    with service.lock:
        service.remover_instancia(db)


@router.post("/instancia/testar", response_model=TelegramInstanciaRead)
def testar_instancia(
    request: Request, db: Session = Depends(get_db), user: Usuario = Depends(require_admin_ou_local)
):
    with service.lock:
        config = service.instancia(db)
        if not config.telegram_token_cifrado:
            raise HTTPException(409, "configure o token do bot primeiro")
        try:
            with service.TelegramClient(config.telegram_token_cifrado) as cliente:
                identidade = cliente.get_me()
                if cliente.webhook_info().get("url"):
                    raise TelegramError("webhook_ativo")
        except TelegramError as exc:
            service.registrar_erro(db, config, None, exc)
            raise UpstreamError(f"não foi possível validar o bot ({exc.codigo})") from None
        config.telegram_username, config.telegram_erro = identidade["username"], None
        config.telegram_url = _origem_instalacao(request)
        db.commit()
        return service.ler_instancia(config)
