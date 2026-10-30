"""Instância do servidor MCP e o que as tools compartilham (docs/mcp.md §3.2).

Toda tool devolve markdown legível (`content`) + os dados crus (`structuredContent`, centavos/ids/
datas ISO) para o agente recalcular ou reformatar conforme o canal. Escritas passam pelos mesmos
endpoints da UI via `api()` — validação, posse e efeitos colaterais (alias de assinatura,
propagação para parcelas) são os do router.
"""

from typing import Annotated, Any

from mcp.server.mcpserver import Context, MCPServer
from mcp_types import CallToolResult, TextContent, ToolAnnotations
from pydantic import Field

from app import __version__
from app.mcp import formato as f
from app.mcp.api import api, categorias, contas, nome_conta, resolver_nome


class MangoMCPServer(MCPServer):
    async def call_tool(self, name, arguments, context=None):
        authorization = (context.headers or {}).get("authorization", "") if context else ""
        if authorization.startswith("Bearer mgi_"):
            from app.services.ia_tools import despachar

            return await despachar(self, name, arguments, context)
        return await super().call_tool(name, arguments, context)


servidor = MangoMCPServer(
    name="mango",
    title="mango — finanças pessoais",
    version=__version__,
    instructions=(
        "Dados financeiros pessoais do usuário no mango: transações, contas, cartões e faturas, "
        "assinaturas, objetivos, orçamentos, investimentos e divisão de contas com outras pessoas. "
        "Valores de entrada em reais (ex.: 39.90); valores de saída em R$ e, no structuredContent, "
        "em centavos. Datas no formato AAAA-MM-DD, fuso America/Sao_Paulo. Onde uma tool pede "
        "categoria, conta, objetivo ou pessoa, aceita o id ou o nome. Use formato='lista' quando o "
        "canal não renderizar tabelas markdown (Telegram, WhatsApp). Antes de alterar dados em "
        "lote, mostre ao usuário o que vai mudar."
    ),
)

LEITURA = ToolAnnotations(read_only_hint=True, open_world_hint=False)
ESCRITA = ToolAnnotations(read_only_hint=False, destructive_hint=False, open_world_hint=False)
IDEMPOTENTE = ToolAnnotations(
    read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=False
)
DESTRUTIVA = ToolAnnotations(read_only_hint=False, destructive_hint=True, open_world_hint=False)

Formato = Annotated[
    f.Formato, Field(description="'tabela' (markdown) ou 'lista' (bullets, p/ chats sem tabela)")
]
NomeOuId = int | str

TIPO_CONTA = {
    "CHECKING_ACCOUNT": "Conta corrente",
    "SAVINGS_ACCOUNT": "Poupança",
    "CREDIT_CARD": "Cartão de crédito",
}


def ok(markdown: str, dados: Any) -> CallToolResult:
    estruturado = dados if isinstance(dados, dict) else {"itens": dados}
    return CallToolResult(content=[TextContent(text=markdown)], structured_content=estruturado)


def juntar(*blocos: str | None) -> str:
    return "\n\n".join(b for b in blocos if b)


async def resolver_categoria(ctx: Context, valor: NomeOuId) -> str:
    return resolver_nome(valor, await categorias(ctx), "categoria")


async def resolver_conta(ctx: Context, valor: NomeOuId) -> int:
    todas = await contas(ctx)
    return resolver_nome(valor, {i: nome_conta(c) for i, c in todas.items()}, "conta")


async def resolver_objetivo(ctx: Context, valor: NomeOuId) -> int:
    objetivos = await api(ctx, "GET", "/objetivos")
    return resolver_nome(valor, {o["id"]: o["titulo"] for o in objetivos}, "objetivo")
