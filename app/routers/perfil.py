"""Router do perfil (§4.1): ler e editar o cadastro do próprio usuário.

Update com campos explícitos (S4) — segredos e `usuario_id` não são atingíveis por aqui.
"""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.exceptions import ConflictError
from app.models.usuario import Usuario
from app.schemas.perfil import (
    BrapiTokenSet,
    BrapiTokenTeste,
    PerfilRead,
    PerfilUpdate,
    TotpConfirmarRequest,
    TotpDesabilitarRequest,
    TotpIniciado,
    TotpIniciarRequest,
)
from app.security import passwords
from app.security.current_user import get_current_user
from app.services import indicadores, totp_perfil
from app.services.brapi import token_brapi

router = APIRouter(prefix="/perfil", tags=["perfil"])


@router.get("", response_model=PerfilRead)
def obter(user: Usuario = Depends(get_current_user)) -> Usuario:
    return user


@router.patch("", response_model=PerfilRead)
def atualizar(
    payload: PerfilUpdate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
) -> Usuario:
    campos = payload.model_dump(exclude_unset=True)
    novo_email = campos.get("email")
    if novo_email and novo_email != user.email:
        existe = db.scalars(select(Usuario).where(Usuario.email == novo_email)).first()
        if existe is not None:
            raise ConflictError("e-mail já em uso")
    # Reobtém na sessão do request para escrever com segurança (nunca confia no objeto externo).
    alvo = db.get(Usuario, user.id)
    for chave, valor in campos.items():
        setattr(alvo, chave, valor)
    db.commit()
    db.refresh(alvo)
    return alvo


# --- token brapi (§4.9): write-only, cifrado em repouso, nunca devolvido (§5.5) --------------


@router.put("/brapi-token", status_code=status.HTTP_204_NO_CONTENT)
def definir_brapi_token(
    payload: BrapiTokenSet,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
) -> None:
    alvo = db.get(Usuario, user.id)
    alvo.brapi_token_cifrado = payload.token.strip()
    db.commit()


@router.delete("/brapi-token", status_code=status.HTTP_204_NO_CONTENT)
def remover_brapi_token(
    db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)
) -> None:
    alvo = db.get(Usuario, user.id)
    alvo.brapi_token_cifrado = None
    db.commit()


@router.post("/brapi-token/testar", response_model=BrapiTokenTeste)
def testar_brapi_token(
    db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)
) -> BrapiTokenTeste:
    """Valida o token guardado contra a brapi (uma cotação curta). Só devolve o booleano."""
    token = token_brapi(db, user.id)
    if not token:
        return BrapiTokenTeste(valida=False)
    hoje = date.today()
    try:
        indicadores.precos_historicos("PETR4", hoje - timedelta(days=7), hoje, token)
        return BrapiTokenTeste(valida=True)
    except indicadores.IndicadorError:
        return BrapiTokenTeste(valida=False)


# --- 2FA (§5.2, #15): cadastrar/trocar/habilitar/desabilitar a exigência no login --------------
# Só existe no self-hosted (modo local não tem `senha_hash` pra reconfirmar via step-up).


def _exigir_self_hosted() -> None:
    if settings.app_mode != "self_hosted":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "não disponível")


def _exigir_senha_atual(user: Usuario, senha_atual: str) -> None:
    """Step-up: cadastrar/trocar/desabilitar reconfirmam a senha atual (proteção contra sessão
    comprometida sequestrar o 2FA da conta). Habilitar não passa por aqui — só reforça segurança."""
    if not passwords.verify_password(senha_atual, user.senha_hash or ""):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "senha atual incorreta")


@router.post("/totp/iniciar", response_model=TotpIniciado)
def iniciar_totp(
    payload: TotpIniciarRequest, user: Usuario = Depends(get_current_user)
) -> TotpIniciado:
    """Passo 1 de cadastrar/trocar o 2FA (mesmo secret novo serve para os dois casos)."""
    _exigir_self_hosted()
    _exigir_senha_atual(user, payload.senha_atual)
    return totp_perfil.iniciar_troca(user)


@router.post("/totp/confirmar", response_model=PerfilRead)
def confirmar_totp(
    payload: TotpConfirmarRequest,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
) -> Usuario:
    """Passo 2: valida o código do novo segredo e só então grava (troca substitui o anterior)."""
    _exigir_self_hosted()
    return totp_perfil.confirmar_troca(db, user, payload.ticket, payload.codigo_totp)


@router.post("/totp/habilitar", status_code=status.HTTP_204_NO_CONTENT)
def habilitar_totp_login(
    db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)
) -> None:
    """Liga a exigência de código no login — sem step-up, só aumenta segurança."""
    _exigir_self_hosted()
    totp_perfil.habilitar_login(db, user)


@router.post("/totp/desabilitar", status_code=status.HTTP_204_NO_CONTENT)
def desabilitar_totp_login(
    payload: TotpDesabilitarRequest,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
) -> None:
    """Desliga a exigência de código no login (o 2FA continua configurado p/ recuperar senha)."""
    _exigir_self_hosted()
    _exigir_senha_atual(user, payload.senha_atual)
    totp_perfil.desabilitar_login(db, user)
