# Desenvolvimento agêntico — setup de ferramentas

Referência para usar **codegraph**, **graphify**, **graphiti**, **ponytail** e **impeccable** num mesmo projeto, com agentes de código (Claude Code, Codex, Cursor etc.). Documento separado da especificação do produto (`Sistema_de_Controle_Financeiro.md`): aqui é **como o ambiente de desenvolvimento é configurado**, não o que o sistema faz.

O objetivo não é "ligar tudo", e sim ter cada ferramenta **disponível e roteável**, carregando o conteúdo dela no contexto **apenas quando for usada**.

> **Nota de faseamento:** boa parte dessas ferramentas (codegraph, graphify) rende mais em base de código **já grande**. Em projeto greenfield vale começar enxuto — ponytail sempre, impeccable nas passadas de UI — e introduzir os grafos de código quando a base já justificar análise de impacto. Para "memória de projeto" no início, um diretório de **ADRs** (decisões em markdown) entrega quase o mesmo do graphiti a custo quase zero.

---

## 1. Princípios

1. **Uma só ferramenta de grafo de código fica conectada por padrão.** As demais entram sob demanda.
2. **Skill em vez de ruleset sempre-ligado** sempre que possível. Skill usa divulgação progressiva: só nome + descrição curta ficam no contexto; o corpo carrega quando o agente invoca.
3. **MCP conectado custa contexto.** Cada servidor MCP injeta as definições das suas ferramentas no prompt. Conecte por sessão, não globalmente, o que não for o "motor do dia a dia".
4. **Hooks automáticos redundantes ficam desligados.** Dois hooks empurrando o agente "para o grafo" a cada turno é desperdício e steering concorrente.
5. **Um router minúsculo no CLAUDE.md** ensina o agente *quando* alcançar cada ferramenta, sem conter a documentação delas.
6. **Só um regime de design por vez:** minimalismo é o padrão (ponytail); embelezamento é um modo invocado (impeccable), não ambiente.

---

## 2. Camadas e papéis

Cada ferramenta ocupa um andar distinto. Só codegraph e graphify se sobrepõem, e essa sobreposição é resolvida por revezamento (seção 4).

| Ferramenta | Camada | Faz |
| --- | --- | --- |
| **codegraph** | Estrutura de código | Grafo de símbolos/chamadas/impacto, rota→handler (FastAPI). Determinístico, 100% local. |
| **graphify** | Mapa amplo | Código + schema SQL/Postgres + docs/PDF num grafo só; relatório e visualização. |
| **graphiti** | Memória de projeto | Grafo temporal de decisões/fatos que evoluem; "por que escolhemos X", o que foi descartado. |
| **ponytail** | Comportamento de código | Escreve o mínimo (YAGNI), sem cortar validação, erro, segurança, acessibilidade. |
| **impeccable** | Design de frontend | Qualidade de UI: tipografia, cor, motion, anti-padrões; comandos de polish/craft/audit. |

---

## 3. Matriz de ativação

| Ferramenta | Mecanismo | Estado padrão | No contexto quando ociosa | Como acionar |
| --- | --- | --- | --- | --- |
| **ponytail** | Ruleset always-on | **Ligado** (`full` ou `lite`) | Apenas o ruleset compacto | Automático; `/ponytail lite\|full\|off` |
| **codegraph** | Servidor MCP | **Conectado** | Defs + guia enxuto (no `initialize` do MCP) | Automático; `codegraph_explore/impact/...` |
| **graphify** | Skill + MCP (sob demanda) | **Skill instalada, hooks DESLIGADOS, MCP não conectado por padrão** | Só a descrição curta da skill | `/graphify .`; `graphify query "..."` ou conectar o MCP na sessão |
| **graphiti** | Serviço (Neo4j/FalkorDB + LLM) + MCP | **Desligado** | Nada | Subir o serviço e conectar o MCP só em sessões de memória |
| **impeccable** | Skill (por comando) | **Instalada, não ambiente** | Só a descrição curta da skill | `/impeccable polish\|craft\|audit`; `npx impeccable detect` em CI |

Regra de ouro: **no máximo um grafo de código conectado por padrão (codegraph)**. graphify e graphiti são MCPs conectados por sessão. ponytail é o único ruleset ambiente, e é pequeno.

---

## 4. Decisões de revezamento

### 4.1 codegraph ↔ graphify (sobreposição de grafo de código)

**codegraph é o motor do dia a dia, sempre conectado.** É o de toque mais leve: entrega a orientação de uso pelo próprio `initialize` do MCP (não escreve no CLAUDE.md), faz auto-sync por eventos do SO e reconhece rotas FastAPI.

**graphify é invocado sob demanda** quando a pergunta cruza fronteiras que o codegraph não cobre — código ↔ schema do Postgres ↔ docs do Pluggy/Open Finance. Use `/graphify .` para gerar/atualizar o mapa, `graphify query` para perguntas pontuais e `graphify export callflow-html` para a página de arquitetura.

**Não rode `graphify claude install`.** Esse é o modo always-on que escreve no CLAUDE.md e instala hook PreToolUse — justamente o que brigaria com o codegraph. Mantenha só a skill (descrição curta) e a invocação manual.

### 4.2 ponytail ↔ impeccable (minimizar vs embelezar)

São tensões reais: ponytail troca um date picker de 404 linhas por `<input type="date">`; impeccable tem `/delight`, `/animate`, `/overdrive` que vão na direção oposta.

Resolução por **modo de uso, não por desligar nenhum**:

- ponytail é o **default ambiente** — minimalismo guarda toda sessão.
- impeccable é **invocado deliberadamente** para a passada de design (`/impeccable craft`, `polish`).
- Dentro de uma invocação do impeccable, a intenção de design tem prioridade; fora dela, ponytail volta a mandar.

A parte do ponytail que nunca cede (validação, erro, segurança, a11y) não conflita com qualidade visual.

### 4.3 graphiti (escopo de sessão)

graphiti é **session-scoped**: conecte o MCP apenas quando a tarefa for registrar/consultar decisões/histórico do projeto. Em sessões normais de código, fica desligado.

---

## 5. Gerenciamento de contexto

- **Divulgação progressiva via skills.** ponytail, impeccable e a skill do graphify instaladas como *skills*, não como blocos colados no CLAUDE.md. O agente vê só nome + descrição; o corpo entra quando invoca.
- **Conexão de MCP por sessão.** codegraph fica conectado (motor); graphify e graphiti só nas sessões que precisam. Para o graphify, exponha só a fatia necessária se houver perfis de ferramenta.
- **Um único ruleset ambiente.** ponytail é o único always-on aceitável porque o texto é curto.
- **Router compacto no CLAUDE.md.** ~15 linhas dizendo *quando* alcançar cada ferramenta. O agente lê o router (barato) e só então carrega a skill ou chama o MCP certo (caro, sob demanda).
- **Desligar hooks redundantes.** Sem `graphify claude install`. codegraph já cobre "consulte o grafo antes de grepar".

---

## 6. Router para colar no CLAUDE.md

Bloco mínimo. Não descreve as ferramentas — só roteia.

```markdown
## Ferramentas de contexto (quando usar cada uma)

- Estrutura de código (quem chama X, raio de impacto, rota→handler): use o MCP **codegraph**
  (codegraph_explore / codegraph_impact). Confie no resultado; não re-grepe.
- Mapa amplo código + schema do banco + docs num grafo só: invoque **graphify** sob demanda
  (`/graphify .`, depois `graphify query`). Não há hook automático — só quando eu pedir.
- Memória do projeto (decisões, "por quê", o que foi descartado, mudanças ao longo do tempo):
  use o MCP **graphiti** SE estiver conectado nesta sessão. Registre decisões relevantes como
  episódio; consulte antes de refazer uma escolha já decidida.
- Trabalho de UI/design: invoque **/impeccable** (craft/polish/audit). Fora de uma passada de
  design, mantenha o padrão minimalista.
- Sempre (ambiente): **ponytail** — escreva só o necessário; nunca corte validação de fronteira,
  tratamento de erro, segurança ou acessibilidade.
```

---

## 7. Setup por ferramenta

**codegraph** — instalar o CLI e conectar o MCP globalmente; inicializar por projeto. Fica conectado.
```
codegraph install
cd <projeto> && codegraph init -i
```

**graphify** — instalar o pacote e a skill, **sem** o modo always-on.
```
uv tool install "graphifyy[sql,postgres,mcp]"
graphify install            # registra a skill (descrição curta)
# NÃO rodar: graphify claude install  (always-on que conflita)
# uso sob demanda:
/graphify .
graphify query "como o modelo de transação se liga às regras de categorização?"
```

**graphiti** — subir banco e MCP só quando for usar memória. Considerar LLM local para custo/privacidade.
```
docker compose up            # Neo4j ou FalkorDB (Kuzu deprecado)
# subir o MCP do graphiti e conectá-lo APENAS nas sessões de memória
# backend local opcional (Ollama) para não mandar metadados a uma API externa
```

**ponytail** — instalar o plugin; default `full` (ou `lite`).
```
/plugin marketplace add DietrichGebert/ponytail
/plugin install ponytail@ponytail
# PONYTAIL_DEFAULT_MODE=full
```

**impeccable** — instalar a skill; usar por comando. O detector roda sem LLM (bom para CI).
```
/impeccable craft        # fluxo de design
/impeccable audit        # checagem técnica (a11y, performance, responsivo)
npx impeccable detect src/   # anti-padrões determinísticos, sem LLM, em CI
```

---

## 8. Fluxos por cenário

| Cenário | Ferramenta(s) | Modo |
| --- | --- | --- |
| Entender ou alterar código existente | codegraph | MCP ativo (explore/impact); ponytail ambiente |
| "Como o código se conecta ao schema e aos docs?" | graphify | sob demanda (`/graphify`, `query`) |
| Refatorar lógica sensível (dedup/categorização) | codegraph (impact) → editar | ponytail ambiente |
| Registrar/relembrar decisão de arquitetura | graphiti | conectar MCP na sessão; gravar/consultar episódio |
| Construir ou refinar UI | impeccable | invocar `/impeccable`; ponytail guarda o "não over-buildar" |
| Antes de commit | ponytail-audit + `impeccable detect` + `codegraph affected` | revisão de over-engineering, anti-padrões, testes afetados |

---

## 9. Guardrails de orçamento de contexto

| Sintoma | Causa provável | Ação |
| --- | --- | --- |
| Agente "esquece" o grafo e volta a grepar | Muita coisa always-on competindo | Reduzir ambiente: ponytail `lite`; conferir que graphify/graphiti não estão conectados à toa |
| Agente ignora o ponytail e over-builda | Steering concorrente (ex.: impeccable ambiente) | Garantir que impeccable é só invocado |
| Respostas lentas/caras sem ganho | Dois grafos de código conectados | Manter só codegraph conectado; graphify sob demanda |
| Memória "vaza" custo de LLM | graphiti conectado sem uso | Conectar graphiti só nas sessões de decisão/histórico |

Princípio: ao notar saturação, **ter menos coisa always-on ao mesmo tempo**, não adicionar mais instrução para "consertar".

---

## 10. Resumo das regras

1. codegraph conectado por padrão. graphify e graphiti por sessão.
2. graphify sem o modo always-on (`graphify claude install` não roda).
3. ponytail é o único ruleset ambiente; em `full` ou `lite`.
4. impeccable só por comando; design é modo, não ambiente.
5. graphiti só em sessões de memória; serviço desligado fora disso.
6. Tudo que puder ser skill, é skill (descrição curta + corpo sob demanda).
7. Router curto no CLAUDE.md roteia; não documenta.
8. Saturação → reduzir o que está always-on, não somar instrução.
9. **Repositório autocontido:** tudo para configurar o ambiente vive no repo.
10. **Artefatos de grafo versionados:** mudanças no codegraph/graphify são commitadas.
11. **Setup executável:** `SETUP.md` é lido por humano e LLM e roda do começo ao fim.

---

## 11. Repositório autocontido

Tudo o que um desenvolvedor (humano ou LLM) precisa para montar o ambiente está **versionado no repositório**. Ninguém depende de configuração manual fora do repo, de variáveis de CI/CD para desenvolver, nem de conhecimento tribal.

Vivem no repo:

- Toolchain e dependências fixadas: `pyproject.toml` + lock do **uv**; `package.json` + lockfile do frontend; versões pinadas (`.python-version`, `.nvmrc`/`.tool-versions`).
- Configuração das ferramentas agênticas: `CLAUDE.md` (router), config do **codegraph**, skill do **graphify**, plugin do **ponytail**, skill do **impeccable**, `docker-compose` do **graphiti** (opt-in).
- Infra local: `docker-compose` do Postgres de desenvolvimento, migrations Alembic.
- Automação: `SETUP.md` (runbook), `scripts/` de bootstrap, `Makefile`/atalhos, hooks de `pre-commit`.

Regra prática: se um passo de setup não está no repo, ele está errado — vira arquivo versionado.

## 12. Artefatos de grafo versionados

As mudanças nos grafos do **codegraph** e do **graphify** são **commitadas**, para que qualquer dev/LLM, ao clonar, já tenha o ambiente atualizado sem regenerar do zero. Diretórios versionados (ex.: `.codegraph/`, `docs/graph/`).

**Cuidado importante (portabilidade × ruído).** Esses grafos auto-sincronizam localmente e podem ser binários ou conter caminhos específicos de máquina — commitar o índice cru gera ruído de diff, conflitos de merge e risco de quebrar para outros. Política recomendada para honrar o objetivo (clone → ambiente atualizado) sem o footgun:

- **Commitar** o(s) **export(es) portáveis e diffáveis** (ex.: grafo do graphify em JSON/HTML, manifesto de símbolos) — é isso que serve de referência compartilhada.
- **Regenerar no setup** o índice local específico de máquina (codegraph) via `SETUP.md`, mantido fresco por um hook.
- **Validar no CI/pre-commit:** um passo regenera e **falha se o artefato versionado estiver desatualizado**, evitando drift entre código e grafo.
- Após mudança estrutural relevante (novos módulos, refactor grande), regenerar e **commitar junto** com a alteração de código.

> Se você preferir commitar o índice cru do codegraph mesmo assim, dá para fazer — só assuma o ruído de diff e configure `.gitattributes` para tratá-lo como binário. A política acima é a que evita dor de merge.

## 13. Documentação de setup (`SETUP.md`)

O repo traz um **`SETUP.md`** que humanos e LLMs leem, e que uma LLM (ex.: Claude Code) **executa de ponta a ponta** para deixar o ambiente pronto. Características:

- **Passos ordenados e idempotentes**, cada um com **comando** e **verificação** (a LLM só avança se a checagem passar).
- **Bootstrap em um comando** (`make setup` / `scripts/setup.sh`) que encadeia tudo, com os passos também detalhados para execução manual.
- Cobre as duas camadas: **toolchain + dependências do projeto** e **ferramentas agênticas + grafos**.
- Termina num **checklist de "pronto para desenvolver"** (testes passando, backend sobe, migrations aplicadas, grafos atualizados).

Ver o próprio `SETUP.md` para o procedimento.
