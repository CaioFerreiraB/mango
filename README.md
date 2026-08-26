<p align="center">
  <img src="frontend/public/illustrations/avatars/logo/mango-logo.png" alt="mango" width="130">
</p>

<h1 align="center">mango</h1>

<p align="center">
  <strong>Suas finanças pessoais no piloto automático — sem planilha.</strong><br>
  Importa tudo sozinho pelo Open Finance e reúne cartões, orçamentos, objetivos e investimentos numa
  visão só — para você fechar o mês em minutos, não em horas.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/status-em%20desenvolvimento-orange" alt="Status: em desenvolvimento">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License: MIT"></a>
  <img src="https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white" alt="Python 3.12">
  <img src="https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/React-20232A?logo=react&logoColor=61DAFB" alt="React">
  <img src="https://img.shields.io/badge/TypeScript-3178C6?logo=typescript&logoColor=white" alt="TypeScript">
  <img src="https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white" alt="Docker">
</p>

---

O **mango** troca a planilha de finanças por um sistema que **importa os dados sozinho** pelo Open
Finance (via [Pluggy](https://pluggy.ai)). Ele trata corretamente **competência × caixa** — a fatura do
cartão não é contada duas vezes —, separa **transferências** das entradas e saídas reais e junta
**orçamentos, objetivos e investimentos** num lugar só. A proposta não é digitar lançamento a
lançamento: é **revisar e confiar** nos números. Feito para **pessoa física no Brasil**, tudo em **R$**
(fuso `America/São_Paulo`) e, por ser **self-hosted**, seus dados ficam no **seu** servidor.

## Screenshots

<!-- Troque os arquivos em docs/screenshots/ pelas suas prints -->
<p align="center">
  <img src="docs/screenshots/dashboard.png" alt="Dashboard" width="49%">
  <img src="docs/screenshots/investimentos.png" alt="Investimentos" width="49%">
</p>

## Recursos

- **Importação automática (Open Finance)** — contas, cartões e investimentos sincronizados via Pluggy.
- **Transações inteligentes** — categorização, detecção automática de transferências entre suas contas
  e marcação de "revisada".
- **Faturas de cartão** — modelo explícito de competência × caixa, para o gasto no cartão não bagunçar
  o fluxo de caixa.
- **Orçamentos** — limites mensais por categoria, com acompanhamento de consumo.
- **Objetivos** — metas com contas e investimentos vinculados e progresso.
- **Assinaturas** — detecção automática de recorrências + cadastro manual, com total mensal.
- **Investimentos** — renda fixa, ações e **FIIs** (proventos e dividend yield), comparação com
  **IBOV, CDI, SELIC e IPCA**, e fundamentos de FII a partir dos dados abertos da **CVM**.
- **Design próprio** — tema claro/escuro, cor de destaque à sua escolha e o mascote mango; interface
  sóbria, sem gamificação.
- **Segurança** — senha (bcrypt), **2FA (TOTP)**, sessões no servidor, CSRF e credenciais do Pluggy
  **cifradas em repouso**.

## Início rápido (self-hosted)

> **Pré-requisitos:** [Docker](https://docs.docker.com/get-docker/) (com Docker Compose) e uma conta no
> [Pluggy](https://pluggy.ai). O mango nasce conectado ao Open Finance, então você precisa das suas
> credenciais (`clientId`, `clientSecret` e um `itemId` já conectado) para concluir o cadastro inicial.
> O cadastro valida a conexão na hora e vincula **uma** instituição financeira; outras conexões você
> adiciona depois em Configurações → Conexões.

A imagem já vem pronta do GHCR: nada é compilado na sua máquina. O clone abaixo serve só para
pegar o compose e gerar as chaves — no Portainer nem isso é necessário.

```bash
git clone https://github.com/CaioFerreiraB/mango.git && cd mango
cp deploy/.env.example deploy/.env
make gen-keys          # gera ENCRYPTION_KEY e SECRET_KEY — cole as duas linhas em deploy/.env
#  … e em deploy/.env: defina POSTGRES_PASSWORD e, para este teste em http://, SESSION_COOKIE_SECURE=false
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d
```

Abra **http://localhost:8000** — o primeiro acesso cai no assistente **/setup**, que cria o usuário
dono, ativa o **2FA** e conecta o Pluggy. Migrations e a carga inicial de categorias rodam sozinhas no
boot.

A stack só escuta em `127.0.0.1` por padrão: para acessar de outra máquina, coloque um reverse proxy
com TLS na frente (o caminho recomendado) — ou mude `BIND_ADDR` conscientemente. Os porquês estão em
[`deploy/README.md`](deploy/README.md).

**No Portainer:** Stacks → Add stack, apontando para `deploy/docker-compose.yml` deste repositório, e
os segredos no painel *Environment variables*. O passo a passo completo — geração das chaves, onde os
segredos ficam, upgrade e backup — está em **[`deploy/README.md`](deploy/README.md)**.

Para rodar a partir do código-fonte (build local em vez da imagem publicada): `make docker-up`.

## Como funciona

Uma única imagem Docker serve a **API (FastAPI)** e a **SPA (React)** no mesmo processo; os dados ficam
num **PostgreSQL** no seu ambiente. A sincronização puxa do Pluggy sob demanda e um agendador cuida das
tarefas periódicas (materialização de orçamento, snapshot de saldo, fundamentos de FII).

**Stack:** Python 3.12 · FastAPI · SQLAlchemy 2 · Alembic · PostgreSQL 16 · React · TypeScript · Vite ·
shadcn/ui · Tailwind.

## Versões e roadmap

Cada versão publicada vira uma imagem no GHCR. O que mudou em cada uma está no
[`CHANGELOG.md`](CHANGELOG.md); o que vem pela frente — e os **problemas conhecidos**, que valem uma
lida antes de expor a instância à internet — está no [`ROADMAP.md`](ROADMAP.md).

## Desenvolvimento

Requer [uv](https://docs.astral.sh/uv/) e Node 20.

```bash
make setup    # dependências, .env, migrations e hooks de pre-commit
make run      # API em modo dev, com reload
make test     # suíte (SQLite; também PostgreSQL quando TEST_DATABASE_URL está definida)
make doctor   # checklist "pronto para desenvolver"
```

Os demais atalhos — build do frontend, geração do cliente tipado, migrations — estão no
[`Makefile`](Makefile).

O projeto segue git flow: toda branch de trabalho sai da `dev` e volta para ela por PR, e a `main`
só recebe merge da `dev`. O fluxo de branches, os portões de qualidade do CI e o processo de release
estão em [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Licença

[MIT](LICENSE) © 2026 Caio Ferreira Bernardo
