"""Router do first-run setup — endpoints PÚBLICOS (rodam antes de existir usuário/sessão).

Dois passos: `POST /setup` gera o QR + ticket (sem gravar nada); `POST /setup/confirmar` exige o
código do autenticador e só então cria o dono e a sessão. Ambos só funcionam uma vez (409 depois).
"""

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.schemas.auth import MeRead
from app.schemas.setup import ConfirmarSetupRequest, SetupIniciado, SetupRequest, SetupStatus
from app.security.sessions import set_session_cookies
from app.security.totp import provisioning_uri
from app.services import setup as setup_service

router = APIRouter(prefix="/setup", tags=["setup"])


@router.get("/status", response_model=SetupStatus)
def status_setup(db: Session = Depends(get_db)) -> SetupStatus:
    return SetupStatus(configured=not setup_service.precisa_setup(db), app_mode=settings.app_mode)


@router.post("", response_model=SetupIniciado)
def iniciar(payload: SetupRequest, db: Session = Depends(get_db)) -> SetupIniciado:
    totp_secret, ticket = setup_service.iniciar_setup(db, payload)
    return SetupIniciado(
        totp_secret=totp_secret,
        totp_provisioning_uri=provisioning_uri(totp_secret, payload.email),
        setup_ticket=ticket,
    )


@router.post("/confirmar", response_model=MeRead, status_code=status.HTTP_201_CREATED)
def confirmar(
    payload: ConfirmarSetupRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> MeRead:
    usuario, sessao = setup_service.confirmar_setup(
        db, payload.setup_ticket, payload.codigo_totp, request
    )
    set_session_cookies(response, sessao)  # já loga o dono (self-hosted é usável na hora)
    return usuario
