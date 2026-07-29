"""Servir a SPA buildada a partir do mesmo servidor FastAPI (§5.1, §5.3).

A API de domínio vive sob ``/api`` (ver ``app.main``); a SPA é dona da raiz. Este módulo monta os
assets com hash e um *fallback* para ``index.html`` nas rotas-cliente (history mode do React
Router), sem tocar em ``/api``, ``/docs``, ``/openapi.json`` nem ``/health``.

Sem build (``frontend/dist`` ausente, ex.: dev ou CI do backend) não monta nada — o servidor segue
API-only. O mesmo comportamento atende self-hosted (atrás de reverse proxy) e desktop (localhost).
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
# Caminhos da raiz que pertencem ao servidor, nunca à SPA.
_RESERVADOS = {"docs", "redoc", "openapi.json", "health"}


def mount_spa(app: FastAPI) -> None:
    """Monta a SPA em ``app`` se houver build. Chamar depois de incluir os routers."""
    index = _DIST / "index.html"
    if not index.is_file():
        return

    assets = _DIST / "assets"
    if assets.is_dir():
        # Arquivos com hash no nome → imutáveis; o StaticFiles cuida de 404/range/etc.
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{caminho:path}", include_in_schema=False)
    def spa(caminho: str) -> FileResponse:
        # Rotas de API/infra inexistentes não devem virar index.html — devolvem 404 de verdade.
        if caminho.startswith("api/") or caminho in _RESERVADOS:
            raise HTTPException(status_code=404)
        # Arquivo solto em dist (favicon, vite.svg, manifest…): serve direto, sem escapar de dist.
        if caminho:
            alvo = (_DIST / caminho).resolve()
            if alvo.is_file() and _DIST in alvo.parents:
                return FileResponse(alvo)
        # Qualquer outra rota é da SPA (deep-link / refresh) → entrega o index.
        return FileResponse(index)
