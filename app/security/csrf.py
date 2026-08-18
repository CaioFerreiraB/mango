"""Proteção CSRF (§5.2) — double-submit cookie sobre a sessão por cookie (#13).

Só age no modo `self_hosted` (o `local` não tem sessão/cookie). Nas mutações da API, exige que o
header `X-CSRF-Token` bata com o cookie `mango_csrf` (que o JS da própria origem lê e ecoa). Um site
de terceiros não consegue ler o cookie para forjar o header; combinado com o cookie de sessão
`SameSite=Lax`, cobre o CSRF sem estado no servidor. Autenticação é separada (cookie de sessão,
validado em `get_current_user`). Os endpoints de bootstrap (setup/login/recuperação) são isentos:
acontecem antes de existir sessão.
"""

import secrets
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from app.config import settings
from app.security.sessions import CSRF_COOKIE, CSRF_HEADER

_METODOS_MUTANTES = {"POST", "PUT", "PATCH", "DELETE"}
# Isentos: bootstrap sem sessão ainda (caminhos completos, com o prefixo /api).
_ISENTOS = {
    "/api/setup",
    "/api/setup/confirmar",
    "/api/auth/login",
    "/api/auth/recuperar-senha",
}
# `app/routers/convite.py` roda inteiro antes de existir sessão (mesmo espírito do bootstrap
# acima), mas o token vai na própria URL (`/api/convites/{token}`) — não dá pra listar como
# caminho exato, então isenta o prefixo inteiro (só tem essas rotas, todas pré-sessão). Seguro
# pelo mesmo motivo do login/setup: não há autoridade ambiente (cookie) a proteger aqui — quem
# não conhece o token/credenciais não consegue nada, então CSRF não se aplica.
_PREFIXOS_ISENTOS = ("/api/convites/",)


def _csrf_valido(request: Request) -> bool:
    cookie = request.cookies.get(CSRF_COOKIE)
    header = request.headers.get(CSRF_HEADER)
    if not cookie or not header:
        return False
    return secrets.compare_digest(cookie, header)


async def csrf_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    if (
        settings.app_mode == "self_hosted"
        and request.method in _METODOS_MUTANTES
        and request.url.path.startswith("/api/")
        and request.url.path not in _ISENTOS
        and not request.url.path.startswith(_PREFIXOS_ISENTOS)
        and not _csrf_valido(request)
    ):
        return JSONResponse(status_code=403, content={"detail": "CSRF token inválido ou ausente"})
    return await call_next(request)
