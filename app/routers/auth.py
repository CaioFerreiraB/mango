"""Autenticação self-hosted (§5.2, #15): login com 2FA, logout, sessão atual e recuperação.

Erros de credencial são propositalmente genéricos (401) para não revelar se o e-mail existe.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.usuario import Sessao, Usuario
from app.schemas.auth import LoginRequest, MeRead, RecuperarSenhaRequest
from app.security import passwords, totp
from app.security.current_user import SESSION_COOKIE, get_current_user
from app.security.sessions import (
    clear_session_cookies,
    criar_sessao,
    revogar_todas,
    set_session_cookies,
)

router = APIRouter(prefix="/auth", tags=["auth"])

_CREDENCIAL_INVALIDA = HTTPException(status.HTTP_401_UNAUTHORIZED, "credenciais inválidas")


def _por_email(db: Session, email: str) -> Usuario | None:
    return db.scalars(select(Usuario).where(Usuario.email == email)).first()


@router.post("/login", response_model=MeRead)
def login(
    payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)
) -> Usuario:
    usuario = _por_email(db, payload.email)
    if usuario is None or not passwords.verify_password(payload.senha, usuario.senha_hash or ""):
        raise _CREDENCIAL_INVALIDA
    if not totp.verificar(usuario.totp_secret_cifrado or "", payload.codigo_totp):
        raise _CREDENCIAL_INVALIDA
    sessao = criar_sessao(db, usuario, request)
    set_session_cookies(response, sessao)
    return usuario


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> None:
    session_id = request.cookies.get(SESSION_COOKIE)
    if session_id:
        sessao = db.get(Sessao, session_id)
        if sessao is not None and sessao.revogada_em is None:
            sessao.revogada_em = datetime.now(UTC)
            db.commit()
    clear_session_cookies(response)


@router.get("/me", response_model=MeRead)
def me(usuario: Usuario = Depends(get_current_user)) -> Usuario:
    return usuario


@router.post("/recuperar-senha", status_code=status.HTTP_204_NO_CONTENT)
def recuperar_senha(payload: RecuperarSenhaRequest, db: Session = Depends(get_db)) -> None:
    usuario = _por_email(db, payload.email)
    # Sem e-mail (#15): o TOTP é a prova de posse. Falha genérica p/ não enumerar contas.
    if usuario is None or not totp.verificar(
        usuario.totp_secret_cifrado or "", payload.codigo_totp
    ):
        raise _CREDENCIAL_INVALIDA
    usuario.senha_hash = passwords.hash_password(payload.nova_senha)
    db.commit()
    revogar_todas(db, usuario.id)  # força re-login em todos os dispositivos
