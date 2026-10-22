"""Tool `grafico` + o recurso do MCP App (docs/mcp.md §3.4). Specs em `app/mcp/vega.py`."""

import base64
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Annotated, Literal

import anyio
from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import CallToolResult, ImageContent, TextContent
from pydantic import Field

from app.mcp import formato as f
from app.mcp import vega
from app.mcp.api import api, categorias, contas, nome_conta
from app.mcp.servidor import (
    LEITURA,
    NomeOuId,
    juntar,
    resolver_conta,
    servidor,
)
from app.services.dashboard import AJUSTE_CATEGORIA_ID
from app.services.periodo import hoje_sp

_URI_APP_GRAFICO = "ui://mango/grafico"
_MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def _mes_rotulo(iso: str) -> str:
    d = date.fromisoformat(iso[:10])
    return f"{_MESES[d.month - 1]}/{d.year % 100:02d}"


@servidor.resource(
    _URI_APP_GRAFICO,
    name="grafico",
    title="Gráfico interativo do mango",
    mime_type="text/html;profile=mcp-app",
    meta={"ui": {"csp": {"resourceDomains": ["https://cdn.jsdelivr.net"]}, "prefersBorder": False}},
)
def app_grafico() -> str:
    """MCP App que desenha o gráfico da tool `grafico` com tooltip e hover."""
    return vega.HTML_APP


Tabela = tuple[list[str], list[list[object]]]


@dataclass(frozen=True)
class _Pedido:
    """Parâmetros da tool `grafico` já com o "hoje" resolvido (cada tipo usa os que lhe cabem)."""

    hoje: date
    inicio: date | None
    fim: date | None
    cartao: NomeOuId | None
    ano: int | None
    mes: int | None


async def _gastos_por_categoria(ctx: Context, p: _Pedido) -> tuple[dict, Tabela]:
    ini, fi = p.inicio or p.hoje.replace(day=1), p.fim or p.hoje
    params = {"inicio": ini.isoformat(), "fim": fi.isoformat()}
    r = await api(ctx, "GET", "/dashboard", params=params)
    cats = await categorias(ctx)
    itens = vega.dobrar_em_outras(
        [
            (cats.get(g["categoria_id"] or "", "Sem categoria"), g["total_centavos"] / 100)
            for g in r["gasto_por_categoria"]
        ]
    )
    spec = vega.barras_horizontais(f"Gastos por categoria — {f.data(ini)} a {f.data(fi)}", itens)
    return spec, (["Categoria", "Total"], [[n, f.brl(round(v * 100))] for n, v in itens])


async def _receitas_vs_despesas(ctx: Context, p: _Pedido) -> tuple[dict, Tabela]:
    fi = p.fim or p.hoje
    ini = p.inicio or (fi.replace(day=1) - timedelta(days=150)).replace(day=1)
    params = {"inicio": ini.isoformat(), "fim": fi.isoformat(), "granularidade": "mensal"}
    buckets = (await api(ctx, "GET", "/dashboard/series", params=params))["buckets"]
    dados = [
        {"periodo": _mes_rotulo(b["inicio"]), "serie": s, "valor": b[k] / 100}
        for b in buckets
        for s, k in (("Entradas", "entradas_centavos"), ("Saídas", "saidas_centavos"))
    ]
    linhas = [
        [_mes_rotulo(b["inicio"])]
        + [f.brl(b[k]) for k in ("entradas_centavos", "saidas_centavos", "resultado_centavos")]
        for b in buckets
    ]
    spec = vega.barras_agrupadas("Entradas × saídas por mês", dados)
    return spec, (["Mês", "Entradas", "Saídas", "Resultado"], linhas)


async def _saldo_contas(ctx: Context, p: _Pedido) -> tuple[dict, Tabela]:
    dias = min(max((p.hoje - p.inicio).days + 1, 2), 365) if p.inicio else 30
    series = await api(ctx, "GET", "/contas/saldos-diarios", params={"dias": dias})
    cts = await contas(ctx)
    series = [s for s in series if s["pontos"] and s["conta_id"] in cts]
    dados = [
        {
            "data": pt["data"],
            "serie": nome_conta(cts[s["conta_id"]]),
            "valor": pt["saldo_centavos"] / 100,
        }
        for s in series
        for pt in s["pontos"]
    ]
    linhas = []
    for s in series:
        primeiro, ultimo = s["pontos"][0]["saldo_centavos"], s["pontos"][-1]["saldo_centavos"]
        linhas.append(
            [
                nome_conta(cts[s["conta_id"]]),
                f.brl(primeiro),
                f.brl(ultimo),
                f.brl(ultimo - primeiro),
            ]
        )
    spec = vega.linhas(f"Saldo das contas — últimos {dias} dias", dados)
    return spec, (["Conta", "Início", "Hoje", "Variação"], linhas)


_SERIES_INVESTIMENTO = (("Patrimônio", "valor_centavos"), ("Investido", "investido_centavos"))


async def _evolucao_investimentos(ctx: Context, p: _Pedido) -> tuple[dict, Tabela]:
    fi = p.fim or p.hoje
    ini = p.inicio or fi - timedelta(days=365)
    params = {"inicio": ini.isoformat(), "fim": fi.isoformat()}
    pontos = (await api(ctx, "GET", "/investimentos/serie", params=params))["pontos"]
    dados = [
        {"data": pt["data"], "serie": s, "valor": pt[k] / 100}
        for pt in pontos
        for s, k in _SERIES_INVESTIMENTO
    ]
    linhas = (
        [[s, f.brl(pontos[0][k]), f.brl(pontos[-1][k])] for s, k in _SERIES_INVESTIMENTO]
        if pontos
        else []
    )
    return vega.linhas("Evolução dos investimentos", dados), (["", "Início", "Fim"], linhas)


async def _orcamento_mes(ctx: Context, p: _Pedido) -> tuple[dict, Tabela]:
    ano, mes = p.ano or p.hoje.year, p.mes or p.hoje.month
    consumo = await api(ctx, "GET", "/orcamentos/consumo", params={"ano": ano, "mes": mes})
    cats = await categorias(ctx)
    despesas = [i for i in consumo["itens"] if not i["suprimido"] and i["tipo"] == "despesa"]
    itens = [
        {
            "categoria": cats.get(i["categoria_id"], i["categoria_id"]),
            "realizado": i["realizado_centavos"] / 100,
            "limite": i["limite_centavos"] / 100,
            "percentual": i["percentual"],
        }
        for i in despesas
    ]
    linhas = [
        [
            cats.get(i["categoria_id"], i["categoria_id"]),
            f.brl(i["realizado_centavos"]),
            f.brl(i["limite_centavos"]),
            f"{i['percentual']}%",
        ]
        for i in despesas
    ]
    spec = vega.orcamento(f"Orçamentos de despesa — {mes:02d}/{ano}", itens)
    return spec, (["Categoria", "Realizado", "Limite", "Uso"], linhas)


def _series_das_faturas(buckets: list[dict], cats: dict[str, str]) -> tuple[list[dict], list[str]]:
    """Categorias de maior gasto somadas nas faturas viram séries (até o teto da paleta, o resto
    vai para "Outras"); o segmento sintético de ajuste é rotulado como no frontend."""
    totais: dict[str, int] = defaultdict(int)
    for b in buckets:
        for g in b["por_categoria"]:
            totais[g["categoria_id"] or ""] += g["total_centavos"]
    principais = sorted(totais, key=lambda c: -totais[c])[: vega.MAX_SERIES - 1]
    rotulos = {**cats, AJUSTE_CATEGORIA_ID: "Encargos e ajustes"}  # total − compras (juros, IOF…)
    nome = {cid: rotulos.get(cid, "Sem categoria") for cid in principais}
    series = [nome[c] for c in principais] + (["Outras"] if len(totais) > len(principais) else [])
    dados = []
    for b in buckets:
        por_serie: dict[str, int] = defaultdict(int)
        for g in b["por_categoria"]:
            por_serie[nome.get(g["categoria_id"] or "", "Outras")] += g["total_centavos"]
        dados += [
            {"periodo": f.data(b["due_date"]), "serie": s, "valor": por_serie[s] / 100, "ordem": i}
            for i, s in enumerate(series)
            if por_serie.get(s)
        ]
    return dados, series


async def _faturas_cartao(ctx: Context, p: _Pedido) -> tuple[dict, Tabela]:
    if p.cartao is None:
        raise ToolError("informe o `cartao` (id ou nome) para faturas_cartao")
    cartao_id = await resolver_conta(ctx, p.cartao)
    caminho = f"/contas/{cartao_id}/faturas-resumo"
    buckets = (await api(ctx, "GET", caminho, params={"limite": 6}))["buckets"]
    dados, series = _series_das_faturas(buckets, await categorias(ctx))
    titulo = f"Faturas — {nome_conta((await contas(ctx))[cartao_id])}"
    linhas = [[f.data(b["due_date"]), f.brl(b["total_centavos"])] for b in buckets]
    return vega.empilhadas(titulo, dados, series), (["Vencimento", "Total"], linhas)


_GERADORES = {
    "gastos_por_categoria": _gastos_por_categoria,
    "receitas_vs_despesas": _receitas_vs_despesas,
    "saldo_contas": _saldo_contas,
    "evolucao_investimentos": _evolucao_investimentos,
    "orcamento_mes": _orcamento_mes,
    "faturas_cartao": _faturas_cartao,
}


@servidor.tool(annotations=LEITURA, meta={"ui": {"resourceUri": _URI_APP_GRAFICO}})
async def grafico(
    ctx: Context,
    tipo: Annotated[
        Literal[tuple(_GERADORES)],  # type: ignore[valid-type]
        Field(
            description="gastos_por_categoria (período; padrão mês atual) · receitas_vs_despesas "
            "(por mês; padrão 6 meses) · saldo_contas (diário; padrão 30 dias) · "
            "evolucao_investimentos (padrão 12 meses) · orcamento_mes (ano/mes) · "
            "faturas_cartao (últimas 6 faturas de `cartao`)"
        ),
    ],
    inicio: date | None = None,
    fim: date | None = None,
    cartao: Annotated[NomeOuId | None, Field(description="Só p/ faturas_cartao")] = None,
    ano: Annotated[int | None, Field(ge=2000, le=2100)] = None,
    mes: Annotated[int | None, Field(ge=1, le=12)] = None,
) -> CallToolResult:
    """Gera um gráfico como imagem PNG (e interativo nos clientes com MCP Apps), sempre junto de
    uma tabela com os mesmos números. Mostre a imagem ao usuário."""
    pedido = _Pedido(hoje_sp(), inicio, fim, cartao, ano, mes)
    spec, tabela = await _GERADORES[tipo](ctx, pedido)
    imagem = await anyio.to_thread.run_sync(vega.png, spec)  # CPU: fora do event loop
    return CallToolResult(
        content=[
            TextContent(text=juntar(f"## {spec['title']}", f.tabela(*tabela))),
            ImageContent(data=base64.b64encode(imagem).decode(), mime_type="image/png"),
        ],
        structured_content={"tipo": tipo, "spec": spec},
    )
