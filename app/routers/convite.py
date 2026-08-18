"""Router PÚBLICO do convite de pessoa "só divisão" (§4.11, §3) — sem `get_current_user`, roda
antes de existir sessão (mesmo espírito de `app/routers/setup.py`). `confirmar` não leva o token
na URL: o ticket cifrado do passo 1 já carrega tudo que precisa (`convite_id` incluso).
"""

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.auth import MeRead
from app.schemas.convite import (
    ConfirmarConviteRequest,
    ConviteStatus,
    IniciarConviteRequest,
    IniciarConviteResponse,
)
from app.security.sessions import set_session_cookies
from app.services import convite as convite_service

router = APIRouter(prefix="/convites", tags=["convite"])


# Declarada antes de `/{token}` — senão "confirmar" seria capturado como o próprio token
# (mesmo cuidado de `/orcamentos/consumo` em app/routers/orcamento.py).
@router.post("/confirmar", response_model=MeRead, status_code=status.HTTP_201_CREATED)
def confirmar(
    payload: ConfirmarConviteRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> MeRead:
    usuario, sessao = convite_service.confirmar(db, payload.ticket, payload.codigo_totp, request)
    set_session_cookies(response, sessao)  # já loga a pessoa convidada (mesmo padrão do setup)
    return usuario


@router.get("/{token}", response_model=ConviteStatus)
def status_convite(token: str, db: Session = Depends(get_db)) -> ConviteStatus:
    return convite_service.status(db, token)


@router.post("/{token}", response_model=IniciarConviteResponse)
def iniciar(
    token: str, payload: IniciarConviteRequest, db: Session = Depends(get_db)
) -> IniciarConviteResponse:
    return convite_service.iniciar(db, token, payload.senha, payload.ativar_totp)
