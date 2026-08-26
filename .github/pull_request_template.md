<!--
Base do PR: `dev`, salvo release/hotfix. Ver CONTRIBUTING.md.
-->

## O que muda

<!-- Uma ou duas frases. O "por quê" importa mais que o "o quê" — o diff já mostra o quê. -->

## Como testar

<!-- Passos para ver funcionando, ou os testes que cobrem isso. -->

## Checklist

- [ ] `make doctor` passa (ruff + pytest + health + build do frontend)
- [ ] Frontend, se mexeu nele: `npm run lint` e `npm run format:check` passam
- [ ] Migration incluída e com `downgrade`, se o modelo mudou (roda em SQLite **e** PostgreSQL)
- [ ] `frontend/openapi.json` regenerado (`make openapi`), se a API mudou
- [ ] Endpoint novo isolado por usuário e coberto em `tests/test_endpoints_isolation.py`
- [ ] `CHANGELOG.md` atualizado, se é mudança visível para quem usa
