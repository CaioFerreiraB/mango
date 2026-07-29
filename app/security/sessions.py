"""Sessões no servidor (#13): ID opaco (não-JWT), revogável, com token CSRF.

O cookie de sessão é `httpOnly` (JS não lê) + `SameSite=Lax` + `Secure` (config). Um segundo
cookie `mango_csrf` — legível pelo JS — carrega o token CSRF que o cliente ecoa no header
`X-CSRF-Token` nas mutações (double-submit, ver `app.security.csrf`).
"""

import secrets
from datetime import UTC, datetime, timedelta

from fastapi import Request, Response
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.config import settings
from app.models.usuario import Sessao, Usuario
from app.security.current_user import SESSION_COOKIE

CSRF_COOKIE = "mango_csrf"
CSRF_HEADER = "X-CSRF-Token"
_DURACAO = timedelta(days=30)


def nova_sessao(usuario_id: int, request: Request | None = None) -> Sessao:
    """Constrói uma `Sessao` (sem persistir) — quem chama decide o commit."""
    agora = datetime.now(UTC)
    return Sessao(
        id=secrets.token_urlsafe(32),
        usuario_id=usuario_id,
        csrf_token=secrets.token_urlsafe(32),
        criado_em=agora,
        expira_em=agora + _DURACAO,
        user_agent=(request.headers.get("user-agent") if request else None),
        ip=(request.client.host if request and request.client else None),
    )


def criar_sessao(db: Session, usuario: Usuario, request: Request | None = None) -> Sessao:
    sessao = nova_sessao(usuario.id, request)
    db.add(sessao)
    db.commit()
    db.refresh(sessao)
    return sessao


def revogar_todas(db: Session, usuario_id: int) -> None:
    """Invalida todas as sessões do usuário (logout global / troca de senha)."""
    db.execute(
        update(Sessao)
        .where(Sessao.usuario_id == usuario_id, Sessao.revogada_em.is_(None))
        .values(revogada_em=datetime.now(UTC))
    )
    db.commit()


def set_session_cookies(response: Response, sessao: Sessao) -> None:
    max_age = int(_DURACAO.total_seconds())
    secure = settings.session_cookie_secure
    response.set_cookie(
        SESSION_COOKIE,
        sessao.id,
        max_age=max_age,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        sessao.csrf_token,
        max_age=max_age,
        httponly=False,
        secure=secure,
        samesite="lax",
        path="/",
    )


def clear_session_cookies(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
