# Instalar o mango (self-hosted)

A imagem publicada em **`ghcr.io/caioferreirab/mango`** serve a API e a interface no mesmo processo.
A stack sobe dois containers: o app e um PostgreSQL. Nenhum build é necessário — há imagem para
`linux/amd64` e `linux/arm64`.

**Pré-requisitos:** Docker (ou Portainer) e uma conta no [Pluggy](https://pluggy.ai) — o mango importa
os dados por Open Finance, então o assistente inicial pede `clientId`, `clientSecret` e um `itemId` já
conectado.

---

## 1. Gere os segredos desta instalação

Duas chaves, geradas por você, uma única vez. Guarde-as: **trocar a `ENCRYPTION_KEY` torna ilegíveis
as credenciais já cifradas no banco.**

```bash
# ENCRYPTION_KEY — cifragem em repouso (Fernet: 32 bytes em base64 url-safe)
docker run --rm python:3.12-slim python -c \
  "import os,base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"

# SECRET_KEY — assinatura das sessões
docker run --rm python:3.12-slim python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Com o repositório clonado, `make gen-keys` faz o mesmo e já imprime no formato do `.env`.

Escolha também uma `POSTGRES_PASSWORD` — **apenas letras e números**, porque o valor entra montado
numa URL de conexão.

## 2. Instale no Portainer

**Stacks → Add stack.** Duas formas:

| Forma | Como |
|---|---|
| **Repository** (acompanha o compose do repo) | Repository URL `https://github.com/CaioFerreiraB/mango`, Reference `refs/heads/main`, Compose path `deploy/docker-compose.yml` |
| **Web editor** | Cole o conteúdo de [`docker-compose.yml`](docker-compose.yml) |

Em **Environment variables** (`Advanced mode` aceita colar tudo de uma vez):

```
ENCRYPTION_KEY=<gerada no passo 1>
SECRET_KEY=<gerada no passo 1>
POSTGRES_PASSWORD=<sua senha>
MANGO_TAG=0.1.0
```

**Deploy the stack.** Se faltar um segredo, o deploy falha dizendo qual — a stack não sobe com valor
em branco.

`MANGO_TAG` fixa a versão da imagem: prefira uma tag explícita a `latest`, para que todo upgrade seja
decisão sua (ver [CHANGELOG.md](../CHANGELOG.md)).

> Sem Portainer, por linha de comando:
> ```bash
> cp deploy/.env.example deploy/.env   # preencha os segredos
> docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d
> ```

### Como você vai alcançar a aplicação

**Por padrão a porta só escuta em `127.0.0.1`** — de propósito. Uma porta publicada pelo Docker é
DNAT em `nat/PREROUTING`: ela **não passa pelo chain `INPUT`**, então um firewall de host escrito em
regras de `INPUT` não a protege, e publicar em `0.0.0.0` colocaria a aplicação na internet sem TLS.
Escolha uma das três:

- **Reverse proxy com TLS na mesma máquina** (recomendado): mantenha o padrão e aponte o proxy para
  `127.0.0.1:8000`.
- **Reverse proxy em container:** remova o bloco `ports` do compose — o proxy alcança o app pela rede
  da stack — e ajuste `FORWARDED_ALLOW_IPS` (abaixo).
- **Acesso direto na rede local** (sem TLS): adicione `BIND_ADDR=0.0.0.0` e `SESSION_COOKIE_SECURE=false`.
  Só faça isso numa rede em que você confia.

### Atrás de um reverse proxy

Duas variáveis:

```
SESSION_COOKIE_SECURE=true        # padrão; o cookie de sessão só trafega em HTTPS
FORWARDED_ALLOW_IPS=127.0.0.1     # padrão
```

Se o proxy roda **noutro container** (Traefik, Caddy, nginx na mesma rede Docker), a requisição chega
de um IP da rede Docker (`172.x`) e o uvicorn descarta os cabeçalhos `X-Forwarded-*`: a aplicação se
enxerga em `http://` mesmo servida por HTTPS, o que quebra redirects e URLs absolutas. Aponte
`FORWARDED_ALLOW_IPS` para a sub-rede do proxy, ou use `*` — **`*` só é seguro se a porta não estiver
publicada em `0.0.0.0`**, senão qualquer um forja o cabeçalho.

Rodando em `http://` para testar? Então `SESSION_COOKIE_SECURE=false`, ou o navegador descarta o
cookie e o login nunca completa.

## 3. Primeiro acesso

Abra a aplicação. O primeiro acesso cai no assistente **/setup**, que cria o usuário dono, ativa o
2FA (TOTP) e conecta o Pluggy. Migrations e a carga inicial de categorias rodam sozinhas no boot —
não há passo manual de banco.

Perdeu o dispositivo do 2FA? Há um backstop por CLI:
`docker compose exec app python -m app.cli reset-password <email> --reset-totp`.

---

## Onde ficam os segredos

Três grupos, com donos diferentes — não os misture:

- **Segredos de build/publicação:** nenhum. O workflow de release usa o `GITHUB_TOKEN` automático do
  GitHub Actions para publicar no GHCR.
- **Segredos desta instalação** (`ENCRYPTION_KEY`, `SECRET_KEY`, `POSTGRES_PASSWORD`): ficam **na
  máquina que roda o container** — nas variáveis de ambiente da stack no Portainer, ou no
  `deploy/.env` (ignorado pelo git, e vale um `chmod 600`). **Nunca no GitHub:** são gerados por quem
  instala, não pertencem ao projeto.
- **Credenciais do Pluggy e token da brapi:** você não configura por ambiente. Entram pela interface
  e ficam **cifrados em repouso** no banco, com a sua `ENCRYPTION_KEY`.

No Portainer CE, as variáveis da stack ficam no `portainer.db` **sem cifragem em repouso**: quem tem
acesso ao volume do Portainer, ou é admin da instância, consegue lê-las. Para a maioria dos usos
domésticos isso é aceitável — quem tem esse acesso já controla o host. Se não for o seu caso, use
Docker secrets abaixo.

### Docker secrets (alternativa)

O app lê automaticamente segredos em `/run/secrets/<nome_do_campo_em_minúsculas>`. Para usar, junte
ao `docker-compose.yml`:

```yaml
services:
  app:
    # remova as linhas ENCRYPTION_KEY / SECRET_KEY do bloco `environment`
    secrets: [encryption_key, secret_key]

secrets:
  encryption_key:
    file: /srv/mango/secrets/encryption_key   # arquivo no host, sem quebra de linha ao final
  secret_key:
    file: /srv/mango/secrets/secret_key
```

Variável de ambiente tem precedência sobre o arquivo: use uma forma ou a outra, nunca as duas para a
mesma chave.

---

## Upgrade

1. Leia o [CHANGELOG.md](../CHANGELOG.md) da versão de destino.
2. **Faça o backup antes de subir a nova imagem.** As migrations rodam sozinhas no boot: quando você
   perceber que a atualização não serviu, o schema já terá mudado, e voltar a imagem antiga não
   desfaz a migration.
3. Portainer: edite a stack, troque `MANGO_TAG`, **Update the stack** com *Re-pull image* ligado.
   Por CLI: `docker compose -f deploy/docker-compose.yml pull && docker compose -f deploy/docker-compose.yml up -d`.

## Backup e restauração

Os dados vivem no volume `mango_pgdata`. Um dump lógico é o suficiente:

```bash
# backup — troque <stack> pelo nome da stack no Portainer
docker exec <stack>-db-1 pg_dump -U mango -d mango > mango-$(date +%F).sql

# restauração num banco vazio
cat mango-2026-08-21.sql | docker exec -i <stack>-db-1 psql -U mango -d mango
```

Guarde a `ENCRYPTION_KEY` junto do dump: **sem ela o backup não é recuperável por inteiro** — as
credenciais do Pluggy estão cifradas com ela.

---

## Antes de expor à internet

Leia os **Problemas conhecidos** em [ROADMAP.md](../ROADMAP.md). Em resumo: os endpoints de
autenticação ainda não têm rate-limiting, então prefira rede local ou VPN (Tailscale/WireGuard) até
que isso seja corrigido.
