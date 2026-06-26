# SETUP — Configuração do ambiente de desenvolvimento

Este documento deixa o ambiente **pronto para começar o desenvolvimento**. Ele é escrito para ser lido por **humanos** e **executado por uma LLM** (ex.: Claude Code), do começo ao fim.

## Como usar

**Humano:** rode o bootstrap de um comando (seção 2) ou siga os passos manuais (seção 4).

**LLM (agente):** execute os passos da seção 4 **em ordem**. Cada passo tem um **comando** e uma **verificação**. Rode o comando, rode a verificação, e **só avance se a verificação passar**. Se uma verificação falhar, pare e reporte o passo e a saída. Todos os passos são **idempotentes**: rodar de novo não quebra nada. Não pule passos; não invente passos fora desta lista.

> Pré-condição: este runbook assume o esqueleto do repositório (criado na Fase 0). Onde um arquivo ainda não existir, o passo indica como criá-lo.

---

## 1. Pré-requisitos

Precisam existir na máquina antes de começar (o bootstrap não os instala):

- **git**
- **Docker** + **Docker Compose** (Postgres de dev e graphiti opcional)
- Acesso à internet para baixar toolchains e pacotes

Tudo o mais (uv, Node, dependências, ferramentas agênticas) é instalado pelos passos abaixo.

Verificação:

```bash
git --version && docker --version && docker compose version
```

---

## 2. Bootstrap em um comando

```bash
make setup
```

`make setup` encadeia todos os passos da seção 4. Para execução manual, controle fino ou diagnóstico, siga a seção 4 passo a passo. O alvo é idempotente.

Verificação final (mesma da seção 5):

```bash
make doctor
```

---

## 3. Convenções

- Comandos rodam a partir da **raiz do repositório**.
- Banco padrão de desenvolvimento: **SQLite** (zero infra). **Postgres** é opcional e sobe via Docker (passo 4.4) — use-o ao mexer em algo sensível a dialeto.
- Valores monetários são **inteiros em centavos** (ver spec). Nada de float.
- Variáveis de ambiente locais ficam em `.env` (a partir de `.env.example`, versionado). **`.env` não é commitado.**

---

## 4. Passos

### 4.1 — Toolchain Python (uv)

Comando:

```bash
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
uv python install
```

Verificação:

```bash
uv --version && uv run python --version
```

### 4.2 — Toolchain Node (frontend)

Instale a versão fixada em `.nvmrc` (use nvm/fnm/asdf, conforme `.tool-versions`).

Comando:

```bash
# exemplo com fnm; ajuste ao gerenciador da máquina
fnm install && fnm use
corepack enable
```

Verificação:

```bash
node --version && npm --version
```

### 4.3 — Dependências do projeto

Comando:

```bash
uv sync                          # backend (Python), a partir do lock
( cd frontend && npm ci )        # frontend, a partir do lockfile
```

Verificação:

```bash
uv run python -c "import fastapi, sqlalchemy, alembic, pyotp"
( cd frontend && npm ls --depth=0 >/dev/null )
```

### 4.4 — Banco de desenvolvimento

SQLite não exige nada. Postgres (opcional) sobe via Docker:

Comando:

```bash
cp -n .env.example .env || true
docker compose up -d db          # serviço Postgres de desenvolvimento
```

Verificação:

```bash
docker compose ps db             # deve aparecer "running"/"healthy"
```

### 4.5 — Migrations

Comando:

```bash
uv run alembic upgrade head
```

Verificação:

```bash
uv run alembic current           # deve apontar para a última revisão (head)
```

### 4.6 — Ferramentas agênticas

Instala o ambiente de contexto descrito em `DESENVOLVIMENTO.md`. **Não** ative o modo always-on do graphify.

Comando:

```bash
# codegraph: motor do dia a dia (fica conectado)
command -v codegraph >/dev/null || codegraph install
codegraph init -i

# graphify: somente skill (sem always-on)
uv tool install "graphifyy[sql,postgres,mcp]"
graphify install
# NÃO rodar: graphify claude install

# ponytail: ruleset ambiente
# /plugin marketplace add DietrichGebert/ponytail
# /plugin install ponytail@ponytail   (via cliente do agente)

# impeccable: skill por comando (sem ambiente)
# instalada como skill; usar via /impeccable

# graphiti: opcional, só em sessões de memória — NÃO sobe por padrão
# docker compose --profile memory up -d   (quando for usar)
```

Verificação:

```bash
codegraph --version && graphify --version
```

### 4.7 — Grafos versionados

Regenera o índice local de máquina (codegraph) e atualiza os exports portáveis versionados (graphify). Ver política em `DESENVOLVIMENTO.md` §12.

Comando:

```bash
codegraph sync                       # reconstrói o índice local
graphify .                           # atualiza o grafo
graphify export callflow-html        # export portável versionado (docs/graph/)
```

Verificação:

```bash
git status --porcelain docs/graph/   # se houver diff, regenerar+commitar junto à mudança de código
```

### 4.8 — Hooks de pre-commit

Comando:

```bash
uv run pre-commit install
```

Verificação:

```bash
uv run pre-commit run --all-files    # lint, format e validação de freshness dos grafos
```

---

## 5. Checklist "pronto para desenvolver"

Rode `make doctor` (ou os comandos abaixo). Todos devem passar:

```bash
uv run pytest -q                     # testes passam
uv run alembic current               # migrations no head
uv run uvicorn app.main:app --port 8000 &   # backend sobe
sleep 2 && curl -fsS http://localhost:8000/health   # healthcheck OK
kill %1
( cd frontend && npm run build )     # frontend buildá e gera o cliente tipado do OpenAPI
codegraph --version >/dev/null       # ferramentas de contexto disponíveis
```

Quando todos passarem, o ambiente está pronto. A partir daqui, o desenvolvimento segue o faseamento da spec (descoberta → Fase 0 → núcleo → ...).

---

## 6. Notas para o agente

- **Idempotência:** reexecutar qualquer passo é seguro. Em dúvida, rode a verificação antes do comando.
- **Não commitar segredos:** `.env` nunca é versionado; use `.env.example`.
- **Grafos:** se o passo 4.7 deixar diffs em `docs/graph/`, isso é esperado após mudanças de código — commite junto. Não commite o índice cru de máquina do codegraph (regenerado localmente).
- **Falha de verificação:** pare, reporte o passo, o comando e a saída. Não improvise um conserto fora deste runbook.
- **Postgres vs SQLite:** o padrão é SQLite; suba o Postgres (4.4) só quando a tarefa exigir paridade de dialeto.
