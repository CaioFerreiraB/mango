"""Entrypoint ASGI: `uvicorn app.main:app`.

Mesmo servidor atende self-hosted e local (§5.1). No boot aplica migrations + seed (§5.4).
"""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app import __version__
from app.db.bootstrap import bootstrap
from app.exceptions import (
    ConflictError,
    DomainError,
    NotFoundError,
    RateLimitError,
    UpstreamError,
    ValidationError,
)
from app.mcp import ciclo_mcp, endpoint_mcp
from app.routers import ROUTERS_ABERTOS_A_TODOS_OS_TIPOS, all_routers
from app.security.csrf import csrf_middleware
from app.security.current_user import exigir_usuario_completo
from app.web import mount_spa

_STATUS_POR_ERRO = {
    NotFoundError: 404,
    ConflictError: 409,
    ValidationError: 422,
    RateLimitError: 429,
    UpstreamError: 502,
}


def _atualizar_fundamentos_fii_boot() -> None:
    """Ingestão de fundamentos de FII no boot do modo local (throttled, resiliente) — thread de
    fundo p/ não bloquear o boot. No self-hosted quem faz é o scheduler (container longevo)."""
    from app.db.session import SessionLocal
    from app.services.cvm_fii import atualizar_fundamentos_fii

    db = SessionLocal()
    try:
        atualizar_fundamentos_fii(db)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    bootstrap()
    # Fundamentos de FII: ingestão no boot em thread de fundo (não bloqueia) nos DOIS modos — um
    # deploy novo popula os fundamentos logo, sem esperar o job mensal. O throttle interno evita
    # re-baixar quando já está fresco.
    import threading

    threading.Thread(target=_atualizar_fundamentos_fii_boot, daemon=True).start()
    # Rotina diária nos dois modos; os jobs mensais/snapshots seguem só no self-hosted.
    from app.services import agendador, rotina_diaria, telegram

    rotina_diaria.recuperar()
    agendador.iniciar()
    telegram.iniciar()
    try:
        async with ciclo_mcp():
            yield
    finally:
        agendador.parar()
        telegram.parar()


app = FastAPI(title="mango", version=__version__, lifespan=lifespan)

# CSRF nas mutações da API (só self-hosted; ver app.security.csrf).
app.middleware("http")(csrf_middleware)


@app.exception_handler(RequestValidationError)
async def _validation_error_handler(request: Request, exc: RequestValidationError):
    if request.url.path.startswith(("/api/telegram", "/api/ia")):
        # O erro padrão do Pydantic ecoa `input`, que pode conter o token write-only.
        return JSONResponse(
            status_code=422,
            content={
                "detail": [
                    {chave: erro[chave] for chave in ("loc", "msg", "type")}
                    for erro in exc.errors()
                ]
            },
        )
    return await request_validation_exception_handler(request, exc)


@app.exception_handler(DomainError)
async def _domain_error_handler(_request: Request, exc: DomainError) -> JSONResponse:
    status_code = next((s for tipo, s in _STATUS_POR_ERRO.items() if isinstance(exc, tipo)), 400)
    return JSONResponse(status_code=status_code, content={"detail": exc.mensagem})


@app.get("/health", tags=["infra"])
def health() -> dict[str, str]:
    return {"status": "ok"}


# Toda a API de domínio vive sob /api para conviver com a SPA na mesma origem: a SPA é dona da raiz
# (/transacoes, /contas/:id …) e a API não colide com suas rotas-cliente. /health, /docs e
# /openapi.json seguem na raiz (infra). Ver app/web.py para o fallback da SPA.
#
# Contas `tipo="divisao"` (§4.11) só acessam os routers em `ROUTERS_ABERTOS_A_TODOS_OS_TIPOS` — o
# gate fica aqui, um único ponto de aplicação, em vez de em cada função de rota.
for _router in all_routers:
    deps = [] if _router in ROUTERS_ABERTOS_A_TODOS_OS_TIPOS else [Depends(exigir_usuario_completo)]
    app.include_router(_router, prefix="/api", dependencies=deps)

# MCP para agentes (docs/mcp.md) — na raiz como /health: é infra de integração, não rota da API.
app.add_api_route("/mcp", endpoint_mcp, methods=["GET", "POST", "DELETE"], include_in_schema=False)

# Fallback da SPA por último, para não ofuscar a API/infra. No-op sem build (frontend/dist).
mount_spa(app)
