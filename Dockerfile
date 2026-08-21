# Imagem única do self-hosted (§5.1): builda a SPA e serve API + estáticos no mesmo ASGI.
# Migrations + seed rodam sozinhos no boot (app.main lifespan → app.db.bootstrap).

# ---- Stage 1: build da SPA (usa o frontend/openapi.json commitado; não precisa do backend) ----
FROM node:20-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json frontend/.npmrc ./
RUN npm ci
COPY frontend/ ./
RUN npm run build   # → /app/frontend/dist

# ---- Stage 2: runtime Python ----
FROM python:3.12-slim AS runtime

# Metadados OCI. `image.source` é o que faz o GHCR ligar o pacote a este repositório (herda
# visibilidade e README na página do pacote). Preenchidos pelo workflow de release a partir da tag.
ARG VERSION=0.0.0-dev
ARG REVISION=unknown
LABEL org.opencontainers.image.title="mango" \
      org.opencontainers.image.description="Controle financeiro pessoal com importação via Open Finance" \
      org.opencontainers.image.source="https://github.com/CaioFerreiraB/mango" \
      org.opencontainers.image.documentation="https://github.com/CaioFerreiraB/mango/blob/main/deploy/README.md" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${REVISION}"
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
# Camada de dependências (cacheável): instala no /app/.venv sem o código da app.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev

COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY --from=frontend /app/frontend/dist ./frontend/dist

# Segredos vêm do ambiente do container (§5.1), nunca embutidos na imagem.
ENV PATH="/app/.venv/bin:$PATH"
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status==200 else 1)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
