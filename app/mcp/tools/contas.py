"""Tools de contas, cartões, faturas e objetivos (docs/mcp.md §1.1)."""

from collections import defaultdict
from typing import Annotated, Literal

from mcp.server.mcpserver import Context
from mcp_types import CallToolResult
from pydantic import Field

from app.mcp import formato as f
from app.mcp.api import api, categorias, contas, nome_conta
from app.mcp.servidor import (
    IDEMPOTENTE,
    LEITURA,
    TIPO_CONTA,
    Formato,
    NomeOuId,
    juntar,
    ok,
    resolver_conta,
    resolver_objetivo,
    servidor,
)
from app.mcp.tools.transacoes import COLUNAS_TRANSACAO, linhas_transacoes, valor_com_sinal

# --- contas, cartões e faturas --------------------------------------------------------------


@servidor.tool(annotations=LEITURA)
async def listar_contas(ctx: Context, formato: Formato = "tabela") -> CallToolResult:
    """Lista as contas bancárias e cartões conectados, com saldo atual e objetivo vinculado.
    Para limites e faturas de cartão, use `listar_cartoes`."""
    itens = await api(ctx, "GET", "/contas")
    objetivos = {o["id"]: o["titulo"] for o in await api(ctx, "GET", "/objetivos")}
    linhas = [
        [
            c["id"],
            nome_conta(c),
            TIPO_CONTA.get(c.get("subtype") or "", c.get("subtype") or c["type"]),
            f.brl(c["saldo_centavos"]),
            objetivos.get(c.get("objetivo_id")),
        ]
        for c in itens
    ]
    total = sum(c["saldo_centavos"] for c in itens if c["type"] == "BANK")
    md = juntar(
        "## Contas",
        f.tabela(["ID", "Conta", "Tipo", "Saldo", "Objetivo"], linhas, formato),
        f"**Saldo total em contas bancárias:** {f.brl(total)}",
    )
    return ok(md, {"contas": itens, "saldo_total_bancos_centavos": total})


@servidor.tool(annotations=LEITURA)
async def obter_conta(ctx: Context, conta: NomeOuId) -> CallToolResult:
    """Detalhe de uma conta: saldo, número, titular, cheque especial, saldos reservados
    (caixinhas) e, se for cartão, limites e datas."""
    c = await api(ctx, "GET", f"/contas/{await resolver_conta(ctx, conta)}")
    campos = [
        ("Tipo", TIPO_CONTA.get(c.get("subtype") or "", c.get("subtype") or c["type"])),
        ("Saldo", f.brl(c["saldo_centavos"])),
        ("Número", c.get("numero")),
        ("Titular", c.get("owner")),
    ]
    if banco := c.get("conta_bancaria"):
        campos += [
            ("Cheque especial contratado", f.brl(banco.get("overdraft_contracted_limit_centavos"))),
            ("Cheque especial usado", f.brl(banco.get("overdraft_used_limit_centavos"))),
            (
                "Investido automaticamente",
                f.brl(banco.get("automatically_invested_balance_centavos")),
            ),
        ]
    if cartao := c.get("cartao"):
        campos += _campos_cartao(cartao)
    reservados = [
        [
            r.get("nome") or r.get("identificacao"),
            f.brl(r.get("valor_centavos")),
            r.get("rem_indexer"),
        ]
        for r in c.get("saldos_reservados", [])
    ]
    md = juntar(
        f"## {nome_conta(c)}",
        "\n".join(f"- **{k}:** {v or '—'}" for k, v in campos),
        "### Saldos reservados\n\n" + f.tabela(["Nome", "Valor", "Indexador"], reservados)
        if reservados
        else None,
    )
    return ok(md, c)


def _campos_cartao(cartao: dict) -> list[tuple[str, object]]:
    limite = cartao.get("credit_limit_centavos")
    disponivel = cartao.get("available_credit_limit_centavos")
    return [
        ("Bandeira", " ".join(filter(None, [cartao.get("brand"), cartao.get("level")]))),
        ("Limite", f.brl(limite)),
        ("Disponível", f.brl(disponivel)),
        (
            "Usado",
            f.brl(limite - disponivel) if limite is not None and disponivel is not None else None,
        ),
        ("Fechamento", f.data(cartao.get("balance_close_date"))),
        ("Vencimento", f.data(cartao.get("balance_due_date"))),
        ("Pagamento mínimo", f.brl(cartao.get("minimum_payment_centavos"))),
    ]


@servidor.tool(annotations=LEITURA)
async def listar_cartoes(ctx: Context, formato: Formato = "tabela") -> CallToolResult:
    """Lista os cartões de crédito com limite, disponível, fatura atual, fechamento e
    vencimento. Para as faturas de um cartão, use `listar_faturas`."""
    cartoes = [c for c in await api(ctx, "GET", "/contas") if c["type"] == "CREDIT"]
    detalhes = [await api(ctx, "GET", f"/contas/{c['id']}") for c in cartoes]
    linhas = []
    for d in detalhes:
        cartao = d.get("cartao") or {}
        limite = cartao.get("credit_limit_centavos")
        disponivel = cartao.get("available_credit_limit_centavos")
        linhas.append(
            [
                d["id"],
                nome_conta(d),
                " ".join(filter(None, [cartao.get("brand"), cartao.get("level")])),
                f.brl(d["saldo_centavos"]),
                f.brl(limite),
                f.brl(disponivel),
                f.pct(100 * (limite - disponivel) / limite, 0)
                if limite and disponivel is not None
                else None,
                f.data(cartao.get("balance_close_date")),
                f.data(cartao.get("balance_due_date")),
            ]
        )
    colunas = [
        "ID",
        "Cartão",
        "Bandeira",
        "Fatura atual",
        "Limite",
        "Disponível",
        "Uso",
        "Fecha",
        "Vence",
    ]
    md = juntar("## Cartões de crédito", f.tabela(colunas, linhas, formato))
    return ok(md, detalhes)


@servidor.tool(annotations=LEITURA)
async def listar_faturas(
    ctx: Context,
    cartao: Annotated[NomeOuId | None, Field(description="Id ou nome do cartão")] = None,
    limite: Annotated[int, Field(ge=1, le=60)] = 12,
    formato: Formato = "tabela",
) -> CallToolResult:
    """Lista as faturas fechadas dos cartões (mais recentes primeiro). Para os lançamentos e a
    quebra por categoria de uma fatura, use `obter_fatura`."""
    cts = await contas(ctx)
    cartao_id = await resolver_conta(ctx, cartao) if cartao is not None else None
    faturas = [x for x in await api(ctx, "GET", "/faturas") if cartao_id in (None, x["cartao_id"])]
    faturas.sort(key=lambda x: x["due_date"], reverse=True)
    faturas = faturas[:limite]
    linhas = [
        [
            x["id"],
            nome_conta(cts[x["cartao_id"]]) if x["cartao_id"] in cts else x["cartao_id"],
            f.data(x["due_date"]),
            f.brl(x["total_amount_centavos"]),
            f.brl(x.get("minimum_payment_centavos")),
        ]
        for x in faturas
    ]
    md = juntar(
        "## Faturas", f.tabela(["ID", "Cartão", "Vencimento", "Total", "Mínimo"], linhas, formato)
    )
    return ok(md, faturas)


async def _todas_transacoes(ctx: Context, params: dict, teto: int = 1000) -> list[dict]:
    itens: list[dict] = []
    while len(itens) < teto:
        pagina = await api(
            ctx, "GET", "/transacoes", params={**params, "limit": 200, "offset": len(itens)}
        )
        itens += pagina["items"]
        if len(itens) >= pagina["total"] or not pagina["items"]:
            break
    return itens


@servidor.tool(annotations=LEITURA)
async def obter_fatura(ctx: Context, fatura_id: int, formato: Formato = "tabela") -> CallToolResult:
    """Detalhe de uma fatura: total, vencimento, gasto por categoria e todos os lançamentos."""
    fatura = await api(ctx, "GET", f"/faturas/{fatura_id}")
    itens = await _todas_transacoes(ctx, {"fatura_id": fatura_id})
    cats, cts = await categorias(ctx), await contas(ctx)
    por_categoria: dict[str, int] = defaultdict(int)
    for t in itens:
        if not t.get("eh_transferencia"):
            por_categoria[t.get("categoria_efetiva_id") or ""] -= valor_com_sinal(t)
    total_gasto = sum(v for v in por_categoria.values() if v > 0)
    linhas_cat = [
        [
            cats.get(cid, "Sem categoria"),
            f.brl(v),
            f.pct(100 * v / total_gasto) if total_gasto else None,
        ]
        for cid, v in sorted(por_categoria.items(), key=lambda kv: -kv[1])
        if v
    ]
    cartao = cts.get(fatura["cartao_id"])
    md = juntar(
        f"## Fatura {f.data(fatura['due_date'])} — {nome_conta(cartao) if cartao else ''}",
        f"**Total:** {f.brl(fatura['total_amount_centavos'])} · "
        f"**Mínimo:** {f.brl(fatura.get('minimum_payment_centavos'))} · "
        f"**Vencimento:** {f.data(fatura['due_date'])}",
        "### Por categoria\n\n" + f.tabela(["Categoria", "Valor", "%"], linhas_cat, formato),
        "### Lançamentos\n\n"
        + f.tabela(COLUNAS_TRANSACAO, linhas_transacoes(itens, cats, cts), formato),
    )
    return ok(
        md,
        {
            "fatura": fatura,
            "por_categoria": [
                {"categoria_id": k or None, "total_centavos": v} for k, v in por_categoria.items()
            ],
            "transacoes": itens,
        },
    )


# --- objetivos ------------------------------------------------------------------------------


@servidor.tool(annotations=LEITURA)
async def listar_objetivos(ctx: Context, formato: Formato = "tabela") -> CallToolResult:
    """Lista os objetivos financeiros com valor-alvo, quanto já foi guardado (soma das contas e
    investimentos vinculados) e o progresso."""
    objetivos = await api(ctx, "GET", "/objetivos")
    linhas = [
        [
            o["id"],
            o["titulo"],
            f.brl(o["valor_alvo_centavos"]),
            f.brl(o["valor_guardado_centavos"]),
            f"{f.barra(o['progresso'])} {f.pct(100 * o['progresso'], 0)}",
        ]
        for o in objetivos
    ]
    md = juntar(
        "## Objetivos",
        f.tabela(["ID", "Objetivo", "Alvo", "Guardado", "Progresso"], linhas, formato),
    )
    return ok(md, objetivos)


@servidor.tool(annotations=LEITURA)
async def obter_objetivo(
    ctx: Context, objetivo: NomeOuId, formato: Formato = "tabela"
) -> CallToolResult:
    """Detalhe de um objetivo com as contas e investimentos vinculados a ele."""
    o = await api(ctx, "GET", f"/objetivos/{await resolver_objetivo(ctx, objetivo)}")
    falta = max(o["valor_alvo_centavos"] - o["valor_guardado_centavos"], 0)
    vinculos = [
        [v["tipo"], v["id"], v.get("nome"), f.brl(v["saldo_centavos"])]
        for v in o.get("vinculos", [])
    ]
    md = juntar(
        f"## {o['titulo']}",
        o.get("descricao"),
        f"{f.barra(o['progresso'])} **{f.pct(100 * o['progresso'], 0)}** — guardado "
        f"{f.brl(o['valor_guardado_centavos'])} de {f.brl(o['valor_alvo_centavos'])} "
        f"(faltam {f.brl(falta)})",
        "### Vinculados\n\n" + f.tabela(["Tipo", "ID", "Nome", "Saldo"], vinculos, formato),
    )
    return ok(md, o)


@servidor.tool(annotations=IDEMPOTENTE)
async def vincular_objetivo(
    ctx: Context,
    tipo: Literal["conta", "investimento"],
    item_id: Annotated[int, Field(description="Id da conta ou do investimento")],
    objetivo: Annotated[NomeOuId | None, Field(description="Id ou título; null desvincula")],
) -> CallToolResult:
    """Vincula (ou desvincula, com objetivo=null) uma conta ou investimento a um objetivo — o
    saldo dele passa a contar como guardado para o objetivo."""
    objetivo_id = await resolver_objetivo(ctx, objetivo) if objetivo is not None else None
    caminho = f"/contas/{item_id}" if tipo == "conta" else f"/investimentos/{item_id}"
    item = await api(ctx, "PATCH", caminho, corpo={"objetivo_id": objetivo_id})
    acao = f"vinculado(a) ao objetivo {objetivo_id}" if objetivo_id else "desvinculado(a)"
    return ok(f"✔ {tipo.capitalize()} {item_id} {acao}.", item)
