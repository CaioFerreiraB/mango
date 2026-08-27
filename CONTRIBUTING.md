# Como contribuir

Setup do ambiente em [`docs/dev/SETUP.md`](docs/dev/SETUP.md). Este documento é sobre **o fluxo de
branches, os portões de qualidade e o processo de release**.

## Fluxo de branches

O projeto segue git flow, com duas branches permanentes:

| Branch | Papel |
| --- | --- |
| `main` | Só código publicado. Todo commit aqui é (ou vira) uma release. |
| `dev` | Integração. É de onde toda branch de trabalho sai e para onde ela volta. |

```
feat/nome-curto ──(squash)──▶ dev ──(merge commit)──▶ main ──▶ tag vX.Y.Z
```

**Toda branch de trabalho sai da `dev` e volta para a `dev` por PR.** A `main` só recebe merge da
`dev` (ou de `release/*` / `hotfix/*`) — quem impõe isso é o job `guard-origem-do-pr` do CI,
obrigatório na `main`: um PR de `feat/…` direto para a `main` falha e não pode ser mergeado.

Prefixos de branch: `feat/`, `fix/`, `chore/`, `docs/`, `refactor/`, `hotfix/`.

```bash
git switch dev && git pull
git switch -c feat/exportar-csv
# ... trabalho, commits ...
git push -u origin feat/exportar-csv
gh pr create --base dev --fill
```

A branch é **apagada automaticamente** quando o PR é mergeado (`delete_branch_on_merge` no
repositório). Depois disso, localmente: `git switch dev && git pull && git fetch --prune`.

### Estratégia de merge

Não é preferência estética — a de `dev → main` é uma exigência do fluxo de release:

| Destino | Método | Por quê |
| --- | --- | --- |
| `→ dev` | **Squash** | Um commit por feature; a dev fica legível. |
| `→ main` | **Merge commit** | Um squash criaria um commit novo, e a tag `vX.Y.Z` — criada na dev — deixaria de ser ancestral da main. A imagem publicada no GHCR ficaria apontando para fora da main. |

Rebase merge está desabilitado no repositório para não sobrar uma terceira opção no menu.

## Portões de qualidade

Rodam em todo PR e precisam passar antes do merge:

| Portão | O que faz | Rodar localmente |
| --- | --- | --- |
| `test` | ruff, migrations em SQLite **e** PostgreSQL, pytest nos dois dialetos, cobertura | `make doctor` / `make cov` |
| `frontend` | eslint, prettier, geração do cliente tipado, typecheck e build do Vite | `cd frontend && npm run lint && npm run format:check && npm run build` |
| `guard-origem-do-pr` | garante a regra "só a dev entra na main" | — |
| Codacy | análise estática (duplicação, complexidade, bandit) e cobertura | — |
| CodeRabbit | revisão automática do diff, em português | — |

Além disso: **CodeQL**, **secret scanning** e **push protection** estão ligados no repositório. A
push protection bloqueia um `git push` que carregue algo com cara de segredo — se acontecer, não
tente contornar: rescreva o commit sem o segredo e **rotacione a chave**, porque ela já esteve num
objeto do git.

Instalar os hooks locais (ruff, formatação, EOF, YAML, merge conflicts) evita a maior parte das
idas e vindas:

```bash
uv run pre-commit install
```

## Release

Rodado a partir da `dev`, com ela já sincronizada e verde:

```bash
git switch dev && git pull
make release v=X.Y.Z          # sincroniza versões, fecha o CHANGELOG, commita e cria a tag local
git show                      # revise antes de empurrar
git push origin dev
gh pr create --base main --head dev --title "release vX.Y.Z"
# mergeie com MERGE COMMIT (nunca squash — a tag ficaria fora da main)
git push origin vX.Y.Z        # dispara .github/workflows/release.yml → publica no GHCR
```

O `make release` commita direto na `dev`, e a `dev` exige PR. Isso funciona porque o mantenedor tem
bypass de admin na ruleset da `dev` — é o único caminho que usa esse bypass de propósito.

## Hotfix

Bug em produção que não pode esperar o ciclo da `dev`:

```bash
git switch main && git pull
git switch -c hotfix/descricao
# ... correção ...
gh pr create --base main --fill    # o guard aceita hotfix/*
```

Depois do merge na `main`, **faça o back-merge**, senão a correção se perde no próximo release:

```bash
gh pr create --base dev --head main --title "back-merge do hotfix na dev"
```

## Convenções de código

- Comentários, docstrings, mensagens de erro e texto de interface em **português**.
- Dinheiro é sempre inteiro em centavos (`*_centavos`), nunca float.
- Toda query filtra por `usuario_id`. Endpoint novo entra em `tests/test_endpoints_isolation.py`.
- Migration precisa de `downgrade` e tem de rodar nos dois dialetos.
- Mudou a API? `make openapi` para regenerar `frontend/openapi.json`, que é a fonte do cliente
  tipado do frontend.
- Frontend: as regras de accent, tokens e ilustrações estão no [`DESIGN.md`](DESIGN.md).

O `.git-blame-ignore-revs` lista os commits puramente mecânicos. Para o `git blame` local pulá-los:

```bash
git config blame.ignoreRevsFile .git-blame-ignore-revs
```
