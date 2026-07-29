"""Resolução do usuário atual — *seam* do isolamento (§5.2).

- `local`: usuário implícito fixo (monousuário, sem login) — get-or-create.
- `self_hosted`: resolve a sessão pelo cookie opaco (#13). O fluxo que *cria* a sessão
  (registro/login) é da Fase 1; o resolvedor já existe para os testes e o isolamento.

Os testes de isolamento sobrescrevem esta dependency (`app.dependency_overrides`) para
fixar "usuário atual = A" vs "B" sem depender do login.
"""

from datetime import UTC, datetime

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.models.usuario import Sessao, Usuario

SESSION_COOKIE = "mango_session"
LOCAL_USER_EMAIL = "local@mango.local"


def _get_or_create_local_user(db: Session) -> Usuario:
    user = db.scalars(select(Usuario).order_by(Usuario.id)).first()
    if user is None:
        user = Usuario(nome="Local", email=LOCAL_USER_EMAIL)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def _resolve_session_user(db: Session, session_id: str | None) -> Usuario:
    if not session_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "sessão ausente")
    sessao = db.get(Sessao, session_id)
    if sessao is None or sessao.revogada_em is not None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "sessão inválida")
    expira_em = sessao.expira_em
    if expira_em.tzinfo is None:  # SQLite devolve naive — assume UTC
        expira_em = expira_em.replace(tzinfo=UTC)
    if expira_em < datetime.now(UTC):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "sessão expirada")
    return db.get(Usuario, sessao.usuario_id)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> Usuario:
    if settings.app_mode == "local":
        return _get_or_create_local_user(db)
    return _resolve_session_user(db, request.cookies.get(SESSION_COOKIE))
