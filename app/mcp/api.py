"""Loopback das tools MCP para a própria API (docs/mcp.md §2).

Cada tool chama `/api/*` em processo (ASGI, sem rede) repassando o `Authorization` do cliente: as
regras, a validação e o isolamento por usuário são os dos routers — o MCP não reimplementa nenhum.
Erro HTTP vira `ToolError`, que chega ao agente como `isError` com a mensagem do router.
"""

import unicodedata
from typing import Any

import httpx
from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError


async def api(
    ctx: Context, metodo: str, caminho: str, *, params: dict | None = None, corpo: Any = None
) -> Any:
    from app.main import app  # tardio: app.main monta o MCP, que importa este módulo

    headers = {}
    autorizacao = (ctx.headers or {}).get("authorization")
    if autorizacao:
        headers["authorization"] = autorizacao
    params = {k: v for k, v in (params or {}).items() if v is not None}
    transporte = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transporte, base_url="http://mango") as cliente:
        resposta = await cliente.request(
            metodo, "/api" + caminho, params=params, json=corpo, headers=headers
        )
    if resposta.status_code >= 400:
        raise ToolError(_mensagem_de_erro(resposta))
    return resposta.json() if resposta.content else None


def _mensagem_de_erro(resposta: httpx.Response) -> str:
    try:
        detalhe = resposta.json().get("detail")
    except ValueError:
        detalhe = None
    if isinstance(detalhe, list):  # 422 do FastAPI: [{loc, msg}, …]
        detalhe = "; ".join(
            f"{'.'.join(map(str, d.get('loc', [])[1:]))}: {d.get('msg')}" for d in detalhe
        )
    return f"{detalhe or 'erro'} (HTTP {resposta.status_code})"


def _norm(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return sem_acento.casefold().strip()


def resolver_nome(valor: int | str, opcoes: dict[Any, str], rotulo: str) -> Any:
    """Id ou nome → id. Nome casa exato (sem caixa/acento); senão um único "contém". Ambiguidade e
    ausência viram erro com os candidatos — nunca um palpite (docs/mcp.md §1.1)."""
    por_id = next((k for k in opcoes if str(k) == str(valor).strip()), None)
    if por_id is not None:
        return por_id
    if isinstance(valor, int) or valor.strip().isdigit():
        raise ToolError(f"{rotulo} {valor} não encontrado(a)")
    alvo = _norm(valor)
    exatos = [k for k, nome in opcoes.items() if _norm(nome) == alvo]
    candidatos = exatos or [k for k, nome in opcoes.items() if alvo in _norm(nome)]
    if len(candidatos) == 1:
        return candidatos[0]
    if not candidatos:
        raise ToolError(f'{rotulo} "{valor}" não encontrado(a)')
    lista = ", ".join(f"{opcoes[k]} (id {k})" for k in candidatos[:10])
    raise ToolError(f'"{valor}" é ambíguo — {rotulo} possíveis: {lista}. Use o id.')


async def categorias(ctx: Context) -> dict[str, str]:
    """{pluggy_id: nome} de todas as categorias visíveis (globais + personalizadas)."""
    itens = await api(ctx, "GET", "/categorias", params={"apenas_ativas": False})
    return {c["pluggy_id"]: c.get("description_translated") or c["description"] for c in itens}


def nome_conta(conta: dict) -> str:
    return conta.get("nome") or conta.get("marketing_name") or f"Conta {conta['id']}"


async def contas(ctx: Context) -> dict[int, dict]:
    return {c["id"]: c for c in await api(ctx, "GET", "/contas")}
