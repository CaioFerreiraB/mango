# MCP do mango

O mango expõe um servidor [MCP](https://modelcontextprotocol.io) para agentes de IA consultarem e
editarem seus dados financeiros: Claude Code, Codex, Open WebUI, VS Code, ou um bot de
Telegram/WhatsApp montado no n8n. O servidor roda dentro do próprio app, em `/mcp`.

**Configurações do sistema não ficam acessíveis por aqui:** perfil, 2FA, credenciais e conexões do
Pluggy, sincronização, usuários, convites, Telegram e as configurações da instância.

## Ativar

Em **Configurações → MCP**:

1. Ligue **Ativar acesso via MCP**. O token é gerado na primeira ativação.
2. Escolha a **permissão**:
   - **Só leitura** consulta os dados;
   - **Leitura e escrita** também revisa, categoriza, mexe em assinaturas e cria divisões.
3. Copie a configuração pronta do seu cliente. O botão de copiar já inclui o token.

O que dá para fazer na aba:

- **Desativar** faz o token parar de funcionar na hora. Ao reativar, o mesmo token volta a valer.
- **Trocar token** gera um novo e invalida o anterior imediatamente.
- **Mostrar** e **Copiar** revelam o token atual, guardado cifrado no servidor.

No **modo local** (desktop) não há token. O MCP atende só a própria máquina (`localhost`), como o
resto do app.

## Conectar

Troque `https://SEU-MANGO` pelo endereço da sua instância e `SEU_TOKEN` pelo token.

**Claude Code**

```sh
claude mcp add --transport http mango https://SEU-MANGO/mcp --header "Authorization: Bearer SEU_TOKEN"
```

**Codex** (`~/.codex/config.toml`)

```toml
[mcp_servers.mango]
url = "https://SEU-MANGO/mcp"
bearer_token_env_var = "MANGO_MCP_TOKEN"   # export MANGO_MCP_TOKEN="SEU_TOKEN"
```

**Open WebUI:** adicione uma conexão de ferramenta do tipo *MCP (Streamable HTTP)* com a URL
`https://SEU-MANGO/mcp` e autenticação *Bearer* com o token.

**Clientes que só falam stdio** (Claude Desktop e afins) usam o
[`mcp-remote`](https://www.npmjs.com/package/mcp-remote) como ponte:

```json
{
  "mcpServers": {
    "mango": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://SEU-MANGO/mcp", "--header", "Authorization: Bearer SEU_TOKEN"]
    }
  }
}
```

> **Exposição:** o ROADMAP ainda lista a falta de rate-limit no login como problema aberto. Mantenha
> a instância em rede local ou atrás de VPN (Tailscale/WireGuard). claude.ai e o ChatGPT web exigem
> OAuth e acesso público para conectores remotos, então ficam fora por enquanto.

## Tools

Valores de entrada em **reais** (`39.90`). Na saída, R$ no texto e **centavos** no
`structuredContent`. Datas em `AAAA-MM-DD`, no fuso America/Sao_Paulo. Onde se pede categoria,
conta, objetivo ou pessoa, vale o **id ou o nome**:

- o nome é comparado sem acento nem caixa;
- se não houver nome exato, vale um "contém" único;
- nome ambíguo devolve erro com os candidatos, nunca um palpite.

**L** = leitura · **E** = escrita (exige permissão de escrita) · **D** = destrutiva (o cliente
pede confirmação).

| Tool | Tipo | O que faz |
|------|------|-----------|
| `listar_transacoes` | L | Todos os filtros da tela: período, conta, categoria, fatura, assinatura, tipo, revisada, pendente de revisão, transferência, com/sem assinatura, busca, ordenação e paginação. Pagamentos de fatura e lançamentos futuros ficam ocultos por padrão, como na tela |
| `buscar_transacoes` | L | Texto na descrição, no estabelecimento, na descrição própria e nas observações (padrão: 12 meses) |
| `obter_transacao` | L | Detalhe, inclusive de onde veio a categoria |
| `atualizar_transacoes` | E | Em lote (até 100): revisada, categoria (ou restaurar a automática), vincular/desvincular assinatura, não é assinatura, transferência, descrição, observações, provento. Resultado por transação |
| `listar_categorias` | L | Árvore de categorias, do banco e personalizadas |
| `listar_contas` / `obter_conta` | L | Saldos, objetivo vinculado, cheque especial, caixinhas |
| `listar_cartoes` | L | Limite, disponível, uso, fatura atual, fechamento e vencimento |
| `listar_faturas` / `obter_fatura` | L | Faturas por cartão; detalhe com gasto por categoria e lançamentos |
| `listar_objetivos` / `obter_objetivo` | L | Progresso, e as contas e investimentos vinculados |
| `vincular_objetivo` | E | Liga ou desliga uma conta ou investimento de um objetivo |
| `listar_assinaturas` | L | Assinaturas e total mensal equivalente |
| `listar_candidatos_assinatura` | L | Recorrências detectadas que ainda não viraram assinatura |
| `criar_assinatura` / `atualizar_assinatura` | E | Cadastrar (ou confirmar candidato), editar, cancelar (`ativa=false`) |
| `rejeitar_candidato_assinatura` | E | Marca as transações do candidato como "não é assinatura" |
| `excluir_assinatura` | D | Apaga de vez |
| `listar_orcamentos` | L | Limite × realizado do mês, % e alertas |
| `listar_pessoas_divisao` | L | Pessoas e saldo com cada uma. A busca nunca devolve e-mail |
| `saldos_divisao` | L | Saldo geral ou com uma pessoa, e as despesas em aberto entre vocês |
| `listar_divisoes` | L | Despesas divididas por escopo |
| `criar_divisao` | E | Racha uma despesa (igualmente/integral). Pessoas por nome; `pago_por="eu"` é o padrão |
| `quitar_divisao` / `reabrir_divisao` | E | Acerta ou reabre uma despesa |
| `excluir_divisao` | D | Apaga uma despesa (só quem criou) |
| `resumo_financeiro` | L | Entradas, saídas, resultado, gasto por categoria, faturas em aberto |
| `resumo_investimentos` / `listar_investimentos` | L | Patrimônio, rentabilidade × CDI, alocação e posições |
| `listar_fontes_de_renda` | L | Fontes de renda cadastradas |
| `grafico` | L | PNG + tabela com os mesmos números + versão interativa. Tipos: `gastos_por_categoria`, `receitas_vs_despesas`, `saldo_contas`, `evolucao_investimentos`, `orcamento_mes`, `faturas_cartao` |

**Prompts prontos:**

- `revisar_pendentes`: sugere categorias para a fila de revisão e só aplica depois da sua
  confirmação;
- `resumo_do_mes`;
- `acerto_de_contas`.

### Formato das respostas

Toda tool devolve duas coisas:

- **markdown** legível: título, tabela ou lista, totais e paginação (`Use offset=50 para ver os
  próximos`);
- **`structuredContent`** com os dados crus, para o agente recalcular ou reformatar.

As tools de listagem aceitam `formato="lista"`, que troca a tabela por bullets. Telegram e WhatsApp
não renderizam tabela markdown.

**Gráficos:** o `grafico` devolve três coisas:

- uma **imagem PNG**, que funciona em quase todo cliente;
- uma **tabela** com os mesmos números, para clientes sem imagem;
- a spec **Vega-Lite**.

Hosts com suporte a [MCP Apps](https://modelcontextprotocol.io/extensions/apps) também mostram a
versão **interativa**: o recurso `ui://mango/grafico` desenha a mesma spec com tooltip e tema
claro/escuro.

## Como funciona (para quem mexe no código)

```
cliente MCP ──HTTP (Streamable, Bearer)──► /mcp  (MCPServer do SDK `mcp`, sem estado)
                                            │ tool → httpx + ASGITransport(app), mesmo Authorization
                                            ▼
                                          /api/*  (routers atuais: validação, posse, regras)
```

- **Tools chamam a própria API em processo** (`app/mcp/api.py`). Nenhuma regra é reimplementada:
  o alias de assinatura, a propagação de categoria para as parcelas e a checagem de posse são as
  dos routers. Erro HTTP vira `isError` com a mensagem do router.
- **Token** (`app/models/acesso_mcp.py`): um por usuário, guardado de duas formas:
  - sha256 para a busca;
  - Fernet para o usuário revelá-lo na aba.
- **`get_current_user`** autentica pelo Bearer e **ignora o cookie** quando o header vem. Isso
  dispensa o CSRF nessas requisições.
- **Alcance do token:** é uma **allowlist** de rotas × métodos, `_ROTAS_TOKEN` em
  `app/security/current_user.py`. O que não estiver lá dá 403, inclusive o próprio `/acesso-mcp`,
  então um agente não lê nem troca o token. Permissão de leitura só faz GET.
- **Tool nova que precise de rota nova:** adicione a rota à allowlist.
- **`/mcp`** é uma rota FastAPI com a dependency `usuario_mcp`, que responde 401 já no handshake.
  O lifespan sobe um gerenciador de sessões novo a cada entrada (`ciclo_mcp`).
- **Gráficos** (`app/mcp/graficos.py`):
  - specs Vega-Lite convertidas em PNG pelo `vl-convert-python`, sem browser, com locale pt-BR;
  - `allowed_base_urls=[]` impede a spec de buscar URLs;
  - a paleta é a validada pela skill dataviz;
  - o HTML do MCP App fica em `app/mcp/ui/grafico.html`.
- **Testes:** `tests/test_mcp.py`, ponta a ponta via `/mcp` com auth real, em SQLite e Postgres.
  Self-check do formatador: `uv run python -m app.mcp.formato`.
