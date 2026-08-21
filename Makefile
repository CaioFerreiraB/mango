# Bootstrap e verificação do ambiente. Requer `uv` no PATH e Node 20 para o frontend.

.PHONY: setup doctor test lint fmt migrate run revision openapi front-setup front-build \
        gen-keys docker-up docker-down release

setup:  ## Instala deps, prepara .env, aplica migrations e instala hooks
	uv sync
	cp -n .env.example .env || true
	uv run alembic upgrade head
	uv run pre-commit install
	@if [ -d frontend ]; then ( cd frontend && npm ci ); else echo "frontend ausente — pulando npm ci"; fi

doctor:  ## Checklist "pronto para desenvolver"
	uv run ruff check
	uv run pytest -q
	uv run alembic current
	uv run python -c "from fastapi.testclient import TestClient; from app.main import app; \
c=TestClient(app); r=c.get('/health'); assert r.status_code==200 and r.json()=={'status':'ok'}, r.text; \
print('health OK')"
	@if [ -d frontend ]; then ( cd frontend && npm run build ); else \
		echo "frontend ausente (sem UI na Fase 0) — passo de build ignorado"; fi

test:  ## Roda a suíte (SQLite por padrão)
	uv run pytest

lint:  ## Lint (ruff)
	uv run ruff check

fmt:  ## Formata (ruff)
	uv run ruff format

migrate:  ## Aplica migrations até head
	uv run alembic upgrade head

revision:  ## Gera migration por autogenerate: make revision m="mensagem"
	uv run alembic revision --autogenerate -m "$(m)"

run:  ## Sobe o servidor de desenvolvimento
	uv run uvicorn app.main:app --reload --port 8000

openapi:  ## Gera frontend/openapi.json a partir do app (sem subir servidor) — fonte do cliente tipado
	uv run python -c "import json; from app.main import app; \
open('frontend/openapi.json','w').write(json.dumps(app.openapi(), indent=2, ensure_ascii=False) + '\n')"

front-setup:  ## Instala deps do frontend a partir do lockfile
	cd frontend && npm ci

front-build:  ## Build da SPA (cliente tipado + Vite) → frontend/dist
	cd frontend && npm run build

gen-keys:  ## Gera ENCRYPTION_KEY e SECRET_KEY para colar no deploy/.env (§5.1/§5.5)
	@python3 -c "import os,base64; print('ENCRYPTION_KEY='+base64.urlsafe_b64encode(os.urandom(32)).decode())"
	@python3 -c "import secrets; print('SECRET_KEY='+secrets.token_urlsafe(48))"

docker-up:  ## Builda do fonte e sobe a stack self-hosted (app + Postgres) em container
	docker compose --env-file deploy/.env -f docker-compose.selfhosted.yml up --build

docker-down:  ## Derruba a stack self-hosted (mantém o volume de dados)
	docker compose --env-file deploy/.env -f docker-compose.selfhosted.yml down

release:  ## Prepara a versão X.Y.Z: sincroniza versões, fecha o CHANGELOG, commita e cria a tag
	@test -n "$(v)" || { echo "uso: make release v=X.Y.Z"; exit 1; }
	uv run python scripts/release.py "$(v)"
