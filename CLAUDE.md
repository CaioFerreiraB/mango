# mango — controle financeiro pessoal

Sistema de acompanhamento financeiro pessoal (FastAPI + React/TypeScript), em dois modos a partir da
mesma base de código: **self-hosted** (multiusuário) e **local/desktop** (monousuário via pywebview).
Spec do produto e setup do ambiente em `docs/dev/` (`requisitos.md`, `SETUP.md`, `DESENVOLVIMENTO.md`).

## Ferramentas de contexto (quando usar cada uma)

- **Sempre (ambiente): ponytail** — escreva só o necessário (YAGNI, stdlib/plataforma primeiro, sem
  abstração não pedida). Nunca corte validação de fronteira, tratamento de erro, segurança ou
  acessibilidade. Já fica ativo via plugin (hook a cada resposta); ajuste com `/ponytail lite|full|off`.
- **Trabalho de UI/design: `/impeccable`** (craft / polish / audit). Fora de uma passada de design,
  mantenha o padrão minimalista do ponytail. Detector sem-LLM para CI: `npx impeccable detect src/`.

> As demais ferramentas do ambiente descrito em `docs/dev/DESENVOLVIMENTO.md` (codegraph, graphify,
> graphiti) entram numa fase futura, quando a base de código justificar. **Ainda não estão
> instaladas — não tente roteá-las nem chamar seus MCPs.**
