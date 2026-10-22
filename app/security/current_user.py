"""Resolução do usuário atual — *seam* do isolamento (§5.2).

- `local`: usuário implícito fixo (monousuário, sem login) — get-or-create.
- `self_hosted`: resolve a sessão pelo cookie opaco (#13) ou, para agentes, o token MCP no header
  `Authorization: Bearer` (docs/mcp.md). Com Bearer presente o cookie é IGNORADO — é isso que
  deixa o CSRF dispensável nessas requisições (`app.security.csrf`).

Os testes de isolamento sobrescrevem esta dependency (`app.dependency_overrides`) para
fixar "usuário atual = A" vs "B" sem depender do login.
"""

import hashlib
from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.models.acesso_mcp import AcessoMcp
from app.models.usuario import Sessao, Usuario

SESSION_COOKIE = "mango_session"
LOCAL_USER_EMAIL = "local@mango.local"

# Rotas que o token MCP alcança (prefixo → métodos). Negação por padrão: o que não está aqui —
# perfil, 2FA, credenciais, sync, admin, setup, configuração, o próprio /acesso-mcp — responde 403
# a um Bearer. Espelha as tools de `app/mcp`; uma tool nova que precise de rota nova entra aqui.
_LEITURA = frozenset({"GET"})
_ESCRITA = frozenset({"GET", "POST", "PATCH", "DELETE"})
_ROTAS_TOKEN: dict[str, frozenset[str]] = {
    "/api/transacoes": _ESCRITA,
    "/api/assinaturas": _ESCRITA,
    "/api/objetivos": _ESCRITA,
    "/api/divisoes-despesa": _ESCRITA,
    "/api/contas": frozenset({"GET", "PATCH"}),  # PATCH = só o vínculo com objetivo
    "/api/investimentos": frozenset({"GET", "PATCH"}),  # idem
    "/api/categorias": _LEITURA,
    "/api/faturas": _LEITURA,
    "/api/orcamentos": _LEITURA,
    "/api/dashboard": _LEITURA,
    "/api/fontes-de-renda": _LEITURA,
    "/api/usuarios/buscar": _LEITURA,
    "/api/configuracao-sistema": _LEITURA,  # a divisão precisa saber se o saldo está otimizado
    "/api/auth/me": _LEITURA,  # o próprio id ("pago por mim" na divisão)
}
# Gravar `ultimo_uso_em` a cada request seria um UPDATE por chamada de tool; 1/min basta pra aba.
_INTERVALO_ULTIMO_USO = timedelta(minutes=1)


def hash_token(token: str) -> str:
    """sha256 do token MCP. Token de 256 bits aleatórios dispensa sal/bcrypt (não há dicionário)."""
    return hashlib.sha256(token.encode()).hexdigest()


def _get_or_create_local_user(db: Session) -> Usuario:
    user = db.scalars(select(Usuario).order_by(Usuario.id)).first()
    if user is None:
        user = Usuario(nome="Local", email=LOCAL_USER_EMAIL)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def _aware(momento: datetime) -> datetime:
    return momento if momento.tzinfo else momento.replace(tzinfo=UTC)  # SQLite devolve naive


def _resolve_session_user(db: Session, session_id: str | None) -> Usuario:
    if not session_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "sessão ausente")
    sessao = db.get(Sessao, session_id)
    if sessao is None or sessao.revogada_em is not None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "sessão inválida")
    if _aware(sessao.expira_em) < datetime.now(UTC):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "sessão expirada")
    usuario = db.get(Usuario, sessao.usuario_id)
    # Conta desativada (§4.11): mesmo sinal genérico de sessão inválida — não revela o motivo.
    if usuario is None or not usuario.ativo:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "sessão inválida")
    return usuario


def bearer(request: Request) -> str | None:
    """O token do header `Authorization: Bearer …`, ou None se o header não vier nesse formato."""
    esquema, _, token = request.headers.get("authorization", "").partition(" ")
    return token.strip() or None if esquema.lower() == "bearer" else None


def usuario_do_token(db: Session, token: str) -> tuple[Usuario, AcessoMcp]:
    """Token válido = existe, acesso ligado e usuário ativo. Qualquer falha dá o mesmo 401
    genérico (não revela se o token existe mas está desligado)."""
    acesso = db.scalars(select(AcessoMcp).where(AcessoMcp.token_hash == hash_token(token))).first()
    usuario = db.get(Usuario, acesso.usuario_id) if acesso is not None and acesso.ativo else None
    if usuario is None or not usuario.ativo:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "token MCP inválido ou desativado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    agora = datetime.now(UTC)
    if acesso.ultimo_uso_em is None or agora - _aware(acesso.ultimo_uso_em) > _INTERVALO_ULTIMO_USO:
        acesso.ultimo_uso_em = agora
        db.commit()
    return usuario, acesso


def _checar_rota_do_token(request: Request, acesso: AcessoMcp) -> None:
    caminho, metodo = request.url.path, request.method
    metodos = next(
        (m for p, m in _ROTAS_TOKEN.items() if caminho == p or caminho.startswith(p + "/")), None
    )
    if metodos is None or metodo not in metodos:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "recurso fora do alcance do token MCP")
    if acesso.escopo != "escrita" and metodo != "GET":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "o token MCP tem permissão só de leitura")


def get_current_user(request: Request, db: Session = Depends(get_db)) -> Usuario:
    if settings.app_mode == "local":
        return _get_or_create_local_user(db)
    token = bearer(request)
    if token is not None:
        usuario, acesso = usuario_do_token(db, token)
        _checar_rota_do_token(request, acesso)
        return usuario
    return _resolve_session_user(db, request.cookies.get(SESSION_COOKIE))


def require_admin(user: Usuario = Depends(get_current_user)) -> Usuario:
    """Gate da gestão de usuários (§4.11): só o dono da instância, só no self-hosted."""
    if settings.app_mode != "self_hosted":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "não disponível")
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "acesso restrito ao administrador")
    return user


def exigir_usuario_completo(user: Usuario = Depends(get_current_user)) -> Usuario:
    """Bloqueia contas `tipo="divisao"` fora do módulo de divisão de contas (§4.11)."""
    if user.tipo != "completo":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "recurso não disponível para este tipo de conta"
        )
    return user
