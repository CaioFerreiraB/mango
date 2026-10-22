"""Servidor MCP do mango (docs/mcp.md) — montado em `/mcp` pelo `app.main`.

Streamable HTTP sem estado (`stateless_http`, respostas JSON): cada POST é independente, então
não há sessão a perder num restart nem afinidade a manter atrás de proxy. A autenticação é a
dependency `usuario_mcp` na própria rota FastAPI — ela respeita os overrides dos testes e já
responde 401 no handshake; as tools repassam o mesmo token à API (`app.mcp.api`).
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from fastapi import Depends, HTTPException, Request, Response, status
from mcp.server.transport_security import TransportSecuritySettings
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.mcp import tools  # noqa: F401 — registra as tools no servidor
from app.mcp.servidor import servidor
from app.models.usuario import Usuario
from app.security.current_user import _get_or_create_local_user, bearer, usuario_do_token

_HOSTS_LOCAIS = {"127.0.0.1", "localhost", "::1"}


@asynccontextmanager
async def ciclo_mcp() -> AsyncIterator[None]:
    """Sobe o gerenciador de sessões do SDK dentro do lifespan do app. Um gerenciador NOVO por
    entrada: o do SDK só pode rodar uma vez, e cada TestClient reentra no lifespan."""
    # A proteção contra DNS rebinding do SDK checa o Host contra uma lista fixa — no self-hosted o
    # host é o do usuário e a proteção real é o token; no local ela é feita em `usuario_mcp`.
    servidor.streamable_http_app(
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
    async with servidor.session_manager.run():
        yield


def _host_local(request: Request) -> bool:
    host = urlsplit("//" + request.headers.get("host", "")).hostname
    origem = request.headers.get("origin")
    return host in _HOSTS_LOCAIS and (origem is None or urlsplit(origem).hostname in _HOSTS_LOCAIS)


def usuario_mcp(request: Request, db: Session = Depends(get_db)) -> Usuario:
    if settings.app_mode == "local":
        # Sem login no modo local: só a própria máquina fala com o MCP. Host/Origin locais barram
        # um site qualquer que tente alcançar o localhost pelo navegador (DNS rebinding).
        if not _host_local(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "MCP local aceita só localhost")
        return _get_or_create_local_user(db)
    token = bearer(request)
    if token is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "token MCP ausente — gere em Configurações → MCP",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return usuario_do_token(db, token)[0]


class _RepasseMcp(Response):
    """Entrega a requisição (receive/send crus) ao transporte do SDK depois da autenticação."""

    def __init__(self) -> None:
        super().__init__()

    async def __call__(self, scope, receive, send) -> None:  # noqa: ANN001
        await servidor.session_manager.handle_request(scope, receive, send)


async def endpoint_mcp(_usuario: Usuario = Depends(usuario_mcp)) -> Response:
    return _RepasseMcp()
