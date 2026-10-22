"""Tools de visão geral: resumo do período, investimentos e fontes de renda (docs/mcp.md §1.1)."""

from datetime import date
from typing import Annotated

from mcp.server.mcpserver import Context
from mcp_types import CallToolResult
from pydantic import Field

from app.mcp import formato as f
from app.mcp.api import api, categorias, contas, nome_conta
from app.mcp.servidor import (
    LEITURA,
    Formato,
    juntar,
    ok,
    servidor,
)

# --- visão geral, investimentos e renda -----------------------------------------------------


@servidor.tool(annotations=LEITURA)
async def resumo_financeiro(
    ctx: Context,
    inicio: Annotated[date | None, Field(description="Padrão: 1º dia do mês atual")] = None,
    fim: Annotated[date | None, Field(description="Padrão: hoje")] = None,
    formato: Formato = "tabela",
) -> CallToolResult:
    """Resumo do período (padrão: mês atual): entradas, saídas, resultado, saldo em contas,
    transações a revisar, gasto por categoria e faturas em aberto. Transferências não contam."""
    params = {"inicio": inicio and inicio.isoformat(), "fim": fim and fim.isoformat()}
    r = await api(ctx, "GET", "/dashboard", params=params)
    cats, cts = await categorias(ctx), await contas(ctx)
    gastos = sorted(r["gasto_por_categoria"], key=lambda g: -g["total_centavos"])
    total = sum(g["total_centavos"] for g in gastos)
    linhas = [
        [
            cats.get(g["categoria_id"] or "", "Sem categoria"),
            f.brl(g["total_centavos"]),
            f.pct(100 * g["total_centavos"] / total) if total else None,
        ]
        for g in gastos
    ]
    faturas = [
        [
            nome_conta(cts[x["cartao_id"]]) if x["cartao_id"] in cts else x["cartao_id"],
            f.data(x["due_date"]),
            f.brl(x["total_amount_centavos"]),
        ]
        for x in r["faturas_abertas"]
    ]
    periodo = f"{f.data(inicio) if inicio else 'início do mês'} a {f.data(fim) if fim else 'hoje'}"
    md = juntar(
        f"## Resumo — {periodo}",
        f"- **Entradas:** {f.brl(r['entradas_centavos'])}\n"
        f"- **Saídas:** {f.brl(r['saidas_centavos'])}\n"
        f"- **Resultado:** {f.brl(r['resultado_centavos'])}\n- **Saldo em contas:** "
        f"{f.brl(r['saldo_total_centavos'])}\n- **Transações a revisar:** {r['nao_revisadas']}",
        "### Gasto por categoria\n\n" + f.tabela(["Categoria", "Total", "%"], linhas, formato),
        "### Faturas em aberto\n\n" + f.tabela(["Cartão", "Vencimento", "Total"], faturas, formato)
        if faturas
        else None,
    )
    r = {k: v for k, v in r.items() if k != "ultimas_transacoes"}
    return ok(md, r)


@servidor.tool(annotations=LEITURA)
async def resumo_investimentos(ctx: Context, formato: Formato = "tabela") -> CallToolResult:
    """Visão geral da carteira: patrimônio, valor investido, resultado, rentabilidade em 12
    meses vs CDI, dividendos do mês e alocação por tipo de ativo."""
    resumo = await api(ctx, "GET", "/investimentos/resumo")
    visao = await api(ctx, "GET", "/investimentos/visao-geral")
    t = resumo["totais"]
    alocacao = [
        [a["tipo"], f.brl(a["valor_centavos"]), f.pct(a["pct"])] for a in resumo["alocacao"]
    ]
    vs_cdi = visao.get("vs_cdi_pp")
    md = juntar(
        "## Investimentos",
        f"- **Patrimônio:** {f.brl(t['valor_centavos'])} (líquido {f.brl(t['liquido_centavos'])})\n"
        f"- **Investido:** {f.brl(t['investido_centavos'])}\n- **Resultado:** "
        f"{f.brl(t['resultado_centavos'])} ({f.pct(t['resultado_pct'])})\n"
        f"- **Rentabilidade 12 meses:** {f.pct(visao.get('rentabilidade_12m_pct'))}"
        + (f" ({vs_cdi:+.1f} p.p. vs CDI)".replace(".", ",", 1) if vs_cdi is not None else "")
        + f"\n- **Dividendos no mês:** {f.brl(visao['dividendos_mes_centavos'])}\n"
        f"- **Ativos:** {t['quantidade_ativos']}",
        "### Alocação\n\n" + f.tabela(["Tipo", "Valor", "%"], alocacao, formato),
    )
    return ok(md, {"totais": t, "alocacao": resumo["alocacao"], "visao_geral": visao})


@servidor.tool(annotations=LEITURA)
async def listar_investimentos(ctx: Context, formato: Formato = "tabela") -> CallToolResult:
    """Posições da carteira (ações, FIIs, renda fixa, Tesouro…) com quantidade, preço médio,
    valor, resultado e participação. Os `ids` servem para `vincular_objetivo`."""
    posicoes = (await api(ctx, "GET", "/investimentos/resumo"))["posicoes"]
    linhas = [
        [
            ", ".join(map(str, p["investimento_ids"])),
            p.get("code") or p.get("nome"),
            p.get("subtype") or p["type"],
            p.get("instituicao"),
            f"{p['quantidade']:g}" if p.get("quantidade") is not None else None,
            f.brl(p.get("preco_medio_centavos")),
            f.brl(p["valor_centavos"]),
            f"{f.brl(p.get('resultado_centavos'))} ({f.pct(p.get('resultado_pct'))})",
            f.pct(p.get("participacao_pct")),
        ]
        for p in posicoes
    ]
    colunas = [
        "IDs",
        "Ativo",
        "Tipo",
        "Instituição",
        "Qtd",
        "Preço médio",
        "Valor",
        "Resultado",
        "% carteira",
    ]
    md = juntar("## Carteira", f.tabela(colunas, linhas, formato))
    return ok(md, posicoes)


@servidor.tool(annotations=LEITURA)
async def listar_fontes_de_renda(ctx: Context, formato: Formato = "tabela") -> CallToolResult:
    """Fontes de renda cadastradas (salário, aluguel, freelas…) com valor estimado e recorrência."""
    itens = await api(ctx, "GET", "/fontes-de-renda")
    linhas = [
        [
            x["id"],
            x["nome"],
            x["tipo"],
            f.brl(x["valor_estimado_centavos"]),
            x["recorrencia"],
            x.get("fonte"),
        ]
        for x in itens
    ]
    md = juntar(
        "## Fontes de renda",
        f.tabela(
            ["ID", "Nome", "Tipo", "Valor estimado", "Recorrência", "Origem"], linhas, formato
        ),
    )
    return ok(md, itens)
