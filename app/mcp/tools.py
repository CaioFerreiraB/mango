"""Tools do MCP do mango (catálogo em docs/mcp.md §1.1).

Toda tool devolve markdown legível (`content`) + os dados crus (`structuredContent`, centavos/ids/
datas ISO) para o agente recalcular ou reformatar conforme o canal. Escritas passam pelos mesmos
endpoints da UI via `api()` — validação, posse e efeitos colaterais (alias de assinatura,
propagação para parcelas) são os do router.
"""

import base64
from collections import defaultdict
from datetime import date, timedelta
from typing import Annotated, Any, Literal

import anyio
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import CallToolResult, ImageContent, TextContent, ToolAnnotations
from pydantic import Field

from app import __version__
from app.mcp import formato as f
from app.mcp import graficos
from app.mcp.api import api, categorias, contas, nome_conta, resolver_nome
from app.services.dashboard import AJUSTE_CATEGORIA_ID
from app.services.periodo import hoje_sp

servidor = MCPServer(
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

_LEITURA = ToolAnnotations(read_only_hint=True, open_world_hint=False)
_ESCRITA = ToolAnnotations(read_only_hint=False, destructive_hint=False, open_world_hint=False)
_IDEMPOTENTE = ToolAnnotations(
    read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=False
)
_DESTRUTIVA = ToolAnnotations(read_only_hint=False, destructive_hint=True, open_world_hint=False)

Formato = Annotated[
    f.Formato, Field(description="'tabela' (markdown) ou 'lista' (bullets, p/ chats sem tabela)")
]
NomeOuId = int | str

_TIPO_CONTA = {
    "CHECKING_ACCOUNT": "Conta corrente",
    "SAVINGS_ACCOUNT": "Poupança",
    "CREDIT_CARD": "Cartão de crédito",
}
_PERIODICIDADES = Literal["mensal", "trimestral", "semestral", "anual", "irregular"]


def _ok(markdown: str, dados: Any) -> CallToolResult:
    estruturado = dados if isinstance(dados, dict) else {"itens": dados}
    return CallToolResult(content=[TextContent(text=markdown)], structured_content=estruturado)


def _md(*blocos: str | None) -> str:
    return "\n\n".join(b for b in blocos if b)


async def _resolver_categoria(ctx: Context, valor: NomeOuId) -> str:
    return resolver_nome(valor, await categorias(ctx), "categoria")


async def _resolver_conta(ctx: Context, valor: NomeOuId) -> int:
    todas = await contas(ctx)
    return resolver_nome(valor, {i: nome_conta(c) for i, c in todas.items()}, "conta")


async def _resolver_objetivo(ctx: Context, valor: NomeOuId) -> int:
    objetivos = await api(ctx, "GET", "/objetivos")
    return resolver_nome(valor, {o["id"]: o["titulo"] for o in objetivos}, "objetivo")


# --- transações -----------------------------------------------------------------------------


def _descricao(t: dict) -> str:
    return t.get("descricao_usuario") or t.get("merchant_nome") or t.get("description") or "—"


def _valor_com_sinal(t: dict) -> int:
    """Despesa negativa, receita positiva. `abs` primeiro: compra de cartão vem DEBIT com valor
    POSITIVO do Pluggy, ao contrário da conta corrente."""
    valor = abs(t["amount_centavos"])
    return -valor if t["type"] == "DEBIT" else valor


def _situacao(t: dict) -> str:
    marcas = ["revisada" if t["revisada"] else "a revisar"]
    if t.get("assinatura_id"):
        marcas.append("assinatura")
    if t.get("eh_transferencia"):
        marcas.append("transferência")
    if (t.get("total_installments") or 0) > 1:
        marcas.append(f"parcela {t.get('installment_number')}/{t['total_installments']}")
    return ", ".join(marcas)


def _linhas_transacoes(itens: list[dict], cats: dict, cts: dict) -> list[list[object]]:
    return [
        [
            t["id"],
            f.data(t["date"]),
            _descricao(t),
            nome_conta(cts[t["conta_id"]]) if t["conta_id"] in cts else t["conta_id"],
            cats.get(t.get("categoria_efetiva_id") or ""),
            f.brl(_valor_com_sinal(t)),
            _situacao(t),
        ]
        for t in itens
    ]


_COLUNAS_TRANSACAO = ["ID", "Data", "Descrição", "Conta", "Categoria", "Valor", "Situação"]


async def _tabela_transacoes(
    ctx: Context, params: dict, formato: f.Formato, titulo: str
) -> CallToolResult:
    pagina = await api(ctx, "GET", "/transacoes", params=params)
    itens, total = pagina["items"], pagina["total"]
    cats, cts = await categorias(ctx), await contas(ctx)
    despesas = sum(v for t in itens if (v := _valor_com_sinal(t)) < 0)
    receitas = sum(v for t in itens if (v := _valor_com_sinal(t)) > 0)
    md = _md(
        f"## {titulo}",
        f.tabela(_COLUNAS_TRANSACAO, _linhas_transacoes(itens, cats, cts), formato),
        f"Nesta página: despesas **{f.brl(despesas)}** · receitas **{f.brl(receitas)}**"
        if itens
        else None,
        f.paginacao(len(itens), total, params.get("offset") or 0),
    )
    return _ok(md, {"total": total, "offset": params.get("offset") or 0, "transacoes": itens})


@servidor.tool(annotations=_LEITURA)
async def listar_transacoes(
    ctx: Context,
    inicio: Annotated[date | None, Field(description="Data inicial (inclusive)")] = None,
    fim: Annotated[date | None, Field(description="Data final (inclusive)")] = None,
    conta: Annotated[NomeOuId | None, Field(description="Id ou nome da conta/cartão")] = None,
    categoria: Annotated[NomeOuId | None, Field(description="Id ou nome da categoria")] = None,
    fatura_id: Annotated[int | None, Field(description="Só as transações desta fatura")] = None,
    assinatura_id: int | None = None,
    tipo: Literal["despesa", "receita"] | None = None,
    revisada: Annotated[bool | None, Field(description="Filtro cru da marcação")] = None,
    pendente_revisao: Annotated[
        bool | None,
        Field(description="True = fila de revisão (respeita a data de corte da revisão)"),
    ] = None,
    eh_transferencia: bool | None = None,
    tem_assinatura: bool | None = None,
    ocultar_pagamento_fatura: bool = True,
    ocultar_futuras: Annotated[bool, Field(description="Esconde parcelas futuras")] = True,
    busca: Annotated[str | None, Field(max_length=200)] = None,
    ordenar_por: Literal["data", "valor"] = "data",
    descendente: bool = True,
    limite: Annotated[int, Field(ge=1, le=200)] = 50,
    offset: Annotated[int, Field(ge=0)] = 0,
    formato: Formato = "tabela",
) -> CallToolResult:
    """Lista transações com os mesmos filtros da tela de Transações (todos combinam por AND).
    Sem datas, traz todo o histórico. Paginada: siga o `offset` indicado no rodapé."""
    params = {
        "inicio": inicio and inicio.isoformat(),
        "fim": fim and fim.isoformat(),
        "conta_id": await _resolver_conta(ctx, conta) if conta is not None else None,
        "categoria_id": await _resolver_categoria(ctx, categoria)
        if categoria is not None
        else None,
        "fatura_id": fatura_id,
        "assinatura_id": assinatura_id,
        "tipo": {"despesa": "DEBIT", "receita": "CREDIT"}.get(tipo or ""),
        "revisada": revisada,
        "pendente_revisao": pendente_revisao,
        "eh_transferencia": eh_transferencia,
        "tem_assinatura": tem_assinatura,
        "ocultar_pagamento_fatura": ocultar_pagamento_fatura,
        "ocultar_futuras": ocultar_futuras,
        "busca": busca,
        "order": "amount_centavos" if ordenar_por == "valor" else "date",
        "descendente": descendente,
        "limit": limite,
        "offset": offset,
    }
    return await _tabela_transacoes(ctx, params, formato, "Transações")


@servidor.tool(annotations=_LEITURA)
async def buscar_transacoes(
    ctx: Context,
    termo: Annotated[str, Field(min_length=1, max_length=200)],
    inicio: Annotated[date | None, Field(description="Padrão: 12 meses atrás")] = None,
    fim: date | None = None,
    limite: Annotated[int, Field(ge=1, le=200)] = 50,
    offset: Annotated[int, Field(ge=0)] = 0,
    formato: Formato = "tabela",
) -> CallToolResult:
    """Pesquisa transações por texto na descrição do banco, no estabelecimento, na descrição
    própria e nas observações (sem diferenciar maiúsculas)."""
    params = {
        "busca": termo,
        "inicio": (inicio or hoje_sp() - timedelta(days=365)).isoformat(),
        "fim": fim and fim.isoformat(),
        "limit": limite,
        "offset": offset,
    }
    return await _tabela_transacoes(ctx, params, formato, f'Transações com "{termo}"')


@servidor.tool(annotations=_LEITURA)
async def obter_transacao(ctx: Context, transacao_id: int) -> CallToolResult:
    """Detalhe completo de uma transação: categoria (e de onde ela veio), conta, fatura,
    parcelas, assinatura vinculada, descrição própria e observações."""
    t = await api(ctx, "GET", f"/transacoes/{transacao_id}")
    cats, cts = await categorias(ctx), await contas(ctx)
    origem = {
        "assinatura": "da assinatura",
        "manual": "escolhida pelo usuário",
        "regra": "regra de categorização",
        "banco": "sugestão do banco",
    }.get(t.get("categoria_origem"), "—")
    campos = [
        ("Data", f.data(t["date"])),
        ("Descrição", _descricao(t)),
        ("Descrição do banco", t.get("description")),
        ("Valor", f.brl(_valor_com_sinal(t))),
        ("Conta", nome_conta(cts[t["conta_id"]]) if t["conta_id"] in cts else t["conta_id"]),
        ("Categoria", f"{cats.get(t.get('categoria_efetiva_id') or '', '—')} ({origem})"),
        ("Situação", _situacao(t)),
        ("Fatura", t.get("bill_id")),
        ("Assinatura", t.get("assinatura_id")),
        ("Observações", t.get("observacoes")),
        ("Status no banco", "pendente" if t.get("status") == "PENDING" else "lançada"),
    ]
    md = _md(f"## Transação #{t['id']}", "\n".join(f"- **{k}:** {v or '—'}" for k, v in campos))
    return _ok(md, t)


@servidor.tool(annotations=_ESCRITA)
async def atualizar_transacoes(
    ctx: Context,
    ids: Annotated[list[int], Field(min_length=1, max_length=100)],
    revisada: bool | None = None,
    categoria: Annotated[
        NomeOuId | None,
        Field(description="Nova categoria (id ou nome). Vale para todas as parcelas da compra."),
    ] = None,
    restaurar_categoria: Annotated[
        bool, Field(description="Volta à categoria automática (regra/banco)")
    ] = False,
    assinatura_id: Annotated[int | None, Field(description="Vincula a esta assinatura")] = None,
    desvincular_assinatura: bool = False,
    nao_e_assinatura: Annotated[
        bool | None, Field(description="True tira a transação da detecção de assinaturas")
    ] = None,
    eh_transferencia: bool | None = None,
    descricao: Annotated[
        str | None, Field(max_length=255, description="Descrição própria; '' apaga")
    ] = None,
    observacoes: Annotated[str | None, Field(max_length=2000, description="'' apaga")] = None,
    provento_id: Annotated[
        int | None, Field(description="Vincula a um provento de investimento")
    ] = None,
    desvincular_provento: bool = False,
) -> CallToolResult:
    """Altera uma ou várias transações de uma vez, com as mesmas regras da tela: marcar como
    revisada, trocar categoria, vincular/desvincular assinatura, marcar transferência, editar
    descrição e observações. Só os campos informados mudam. Devolve o resultado por transação."""
    if assinatura_id is not None and desvincular_assinatura:
        raise ToolError("informe assinatura_id OU desvincular_assinatura, não os dois")
    if categoria is not None and restaurar_categoria:
        raise ToolError("informe categoria OU restaurar_categoria, não os dois")
    payload: dict[str, Any] = {}
    if revisada is not None:
        payload["revisada"] = revisada
    if categoria is not None:
        payload["categoria_override_id"] = await _resolver_categoria(ctx, categoria)
        payload["categoria_ajustada_usuario"] = True
    if restaurar_categoria:
        payload["categoria_override_id"] = None
        payload["categoria_ajustada_usuario"] = False
    if assinatura_id is not None or desvincular_assinatura:
        payload["assinatura_id"] = assinatura_id
    if nao_e_assinatura is not None:
        payload["nao_e_assinatura"] = nao_e_assinatura
    if eh_transferencia is not None:
        payload["eh_transferencia"] = eh_transferencia
    if descricao is not None:
        payload["descricao_usuario"] = descricao
    if observacoes is not None:
        payload["observacoes"] = observacoes
    if provento_id is not None or desvincular_provento:
        payload["investimento_transacao_id"] = provento_id
    if not payload:
        raise ToolError("nenhum campo para alterar")

    ok, falhas, parcelas = [], [], 0
    for transacao_id in dict.fromkeys(ids):  # sem repetir, na ordem dada
        try:
            t = await api(ctx, "PATCH", f"/transacoes/{transacao_id}", corpo=payload)
        except ToolError as erro:
            falhas.append({"id": transacao_id, "erro": str(erro)})
            continue
        ok.append(t)
        parcelas += t.get("parcelas_atualizadas", 0)
    md = _md(
        f"✔ {len(ok)} de {len(ok) + len(falhas)} transação(ões) atualizada(s)."
        + (
            f" Outras {parcelas} parcela(s) da mesma compra foram recategorizadas."
            if parcelas
            else ""
        ),
        f.tabela(["ID", "Erro"], [[x["id"], x["erro"]] for x in falhas]) if falhas else None,
    )
    return _ok(md, {"atualizadas": ok, "falhas": falhas, "parcelas_atualizadas": parcelas})


@servidor.tool(annotations=_LEITURA)
async def listar_categorias(
    ctx: Context,
    busca: Annotated[str | None, Field(description="Filtra pelo nome")] = None,
    apenas_ativas: bool = True,
    formato: Formato = "tabela",
) -> CallToolResult:
    """Lista as categorias (do banco e personalizadas) em árvore — use o id ou o nome em
    `atualizar_transacoes`, `criar_assinatura` e `criar_divisao`."""
    itens = await api(ctx, "GET", "/categorias", params={"apenas_ativas": apenas_ativas})
    nomes = {c["pluggy_id"]: c.get("description_translated") or c["description"] for c in itens}
    if busca:
        termo = busca.casefold()
        itens = [c for c in itens if termo in nomes[c["pluggy_id"]].casefold()]
    # Pai antes dos filhos; filhos agrupados sob o pai.
    itens.sort(
        key=lambda c: (
            nomes.get(c.get("parent_id") or c["pluggy_id"], ""),
            bool(c.get("parent_id")),
            nomes[c["pluggy_id"]],
        )
    )
    linhas = [
        [
            c["pluggy_id"],
            ("↳ " if c.get("parent_id") else "") + nomes[c["pluggy_id"]],
            nomes.get(c.get("parent_id") or ""),
            "personalizada" if c.get("personalizada") else "banco",
        ]
        for c in itens
    ]
    md = _md("## Categorias", f.tabela(["ID", "Categoria", "Pai", "Origem"], linhas, formato))
    return _ok(md, itens)


# --- contas, cartões e faturas --------------------------------------------------------------


@servidor.tool(annotations=_LEITURA)
async def listar_contas(ctx: Context, formato: Formato = "tabela") -> CallToolResult:
    """Lista as contas bancárias e cartões conectados, com saldo atual e objetivo vinculado.
    Para limites e faturas de cartão, use `listar_cartoes`."""
    itens = await api(ctx, "GET", "/contas")
    objetivos = {o["id"]: o["titulo"] for o in await api(ctx, "GET", "/objetivos")}
    linhas = [
        [
            c["id"],
            nome_conta(c),
            _TIPO_CONTA.get(c.get("subtype") or "", c.get("subtype") or c["type"]),
            f.brl(c["saldo_centavos"]),
            objetivos.get(c.get("objetivo_id")),
        ]
        for c in itens
    ]
    total = sum(c["saldo_centavos"] for c in itens if c["type"] == "BANK")
    md = _md(
        "## Contas",
        f.tabela(["ID", "Conta", "Tipo", "Saldo", "Objetivo"], linhas, formato),
        f"**Saldo total em contas bancárias:** {f.brl(total)}",
    )
    return _ok(md, {"contas": itens, "saldo_total_bancos_centavos": total})


@servidor.tool(annotations=_LEITURA)
async def obter_conta(ctx: Context, conta: NomeOuId) -> CallToolResult:
    """Detalhe de uma conta: saldo, número, titular, cheque especial, saldos reservados
    (caixinhas) e, se for cartão, limites e datas."""
    c = await api(ctx, "GET", f"/contas/{await _resolver_conta(ctx, conta)}")
    campos = [
        ("Tipo", _TIPO_CONTA.get(c.get("subtype") or "", c.get("subtype") or c["type"])),
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
    md = _md(
        f"## {nome_conta(c)}",
        "\n".join(f"- **{k}:** {v or '—'}" for k, v in campos),
        "### Saldos reservados\n\n" + f.tabela(["Nome", "Valor", "Indexador"], reservados)
        if reservados
        else None,
    )
    return _ok(md, c)


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


@servidor.tool(annotations=_LEITURA)
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
    md = _md("## Cartões de crédito", f.tabela(colunas, linhas, formato))
    return _ok(md, detalhes)


@servidor.tool(annotations=_LEITURA)
async def listar_faturas(
    ctx: Context,
    cartao: Annotated[NomeOuId | None, Field(description="Id ou nome do cartão")] = None,
    limite: Annotated[int, Field(ge=1, le=60)] = 12,
    formato: Formato = "tabela",
) -> CallToolResult:
    """Lista as faturas fechadas dos cartões (mais recentes primeiro). Para os lançamentos e a
    quebra por categoria de uma fatura, use `obter_fatura`."""
    cts = await contas(ctx)
    cartao_id = await _resolver_conta(ctx, cartao) if cartao is not None else None
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
    md = _md(
        "## Faturas", f.tabela(["ID", "Cartão", "Vencimento", "Total", "Mínimo"], linhas, formato)
    )
    return _ok(md, faturas)


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


@servidor.tool(annotations=_LEITURA)
async def obter_fatura(ctx: Context, fatura_id: int, formato: Formato = "tabela") -> CallToolResult:
    """Detalhe de uma fatura: total, vencimento, gasto por categoria e todos os lançamentos."""
    fatura = await api(ctx, "GET", f"/faturas/{fatura_id}")
    itens = await _todas_transacoes(ctx, {"fatura_id": fatura_id})
    cats, cts = await categorias(ctx), await contas(ctx)
    por_categoria: dict[str, int] = defaultdict(int)
    for t in itens:
        if not t.get("eh_transferencia"):
            por_categoria[t.get("categoria_efetiva_id") or ""] -= _valor_com_sinal(t)
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
    md = _md(
        f"## Fatura {f.data(fatura['due_date'])} — {nome_conta(cartao) if cartao else ''}",
        f"**Total:** {f.brl(fatura['total_amount_centavos'])} · "
        f"**Mínimo:** {f.brl(fatura.get('minimum_payment_centavos'))} · "
        f"**Vencimento:** {f.data(fatura['due_date'])}",
        "### Por categoria\n\n" + f.tabela(["Categoria", "Valor", "%"], linhas_cat, formato),
        "### Lançamentos\n\n"
        + f.tabela(_COLUNAS_TRANSACAO, _linhas_transacoes(itens, cats, cts), formato),
    )
    return _ok(
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


@servidor.tool(annotations=_LEITURA)
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
    md = _md(
        "## Objetivos",
        f.tabela(["ID", "Objetivo", "Alvo", "Guardado", "Progresso"], linhas, formato),
    )
    return _ok(md, objetivos)


@servidor.tool(annotations=_LEITURA)
async def obter_objetivo(
    ctx: Context, objetivo: NomeOuId, formato: Formato = "tabela"
) -> CallToolResult:
    """Detalhe de um objetivo com as contas e investimentos vinculados a ele."""
    o = await api(ctx, "GET", f"/objetivos/{await _resolver_objetivo(ctx, objetivo)}")
    falta = max(o["valor_alvo_centavos"] - o["valor_guardado_centavos"], 0)
    vinculos = [
        [v["tipo"], v["id"], v.get("nome"), f.brl(v["saldo_centavos"])]
        for v in o.get("vinculos", [])
    ]
    md = _md(
        f"## {o['titulo']}",
        o.get("descricao"),
        f"{f.barra(o['progresso'])} **{f.pct(100 * o['progresso'], 0)}** — guardado "
        f"{f.brl(o['valor_guardado_centavos'])} de {f.brl(o['valor_alvo_centavos'])} "
        f"(faltam {f.brl(falta)})",
        "### Vinculados\n\n" + f.tabela(["Tipo", "ID", "Nome", "Saldo"], vinculos, formato),
    )
    return _ok(md, o)


@servidor.tool(annotations=_IDEMPOTENTE)
async def vincular_objetivo(
    ctx: Context,
    tipo: Literal["conta", "investimento"],
    id: Annotated[int, Field(description="Id da conta ou do investimento")],
    objetivo: Annotated[NomeOuId | None, Field(description="Id ou título; null desvincula")],
) -> CallToolResult:
    """Vincula (ou desvincula, com objetivo=null) uma conta ou investimento a um objetivo — o
    saldo dele passa a contar como guardado para o objetivo."""
    objetivo_id = await _resolver_objetivo(ctx, objetivo) if objetivo is not None else None
    caminho = f"/contas/{id}" if tipo == "conta" else f"/investimentos/{id}"
    item = await api(ctx, "PATCH", caminho, corpo={"objetivo_id": objetivo_id})
    acao = f"vinculado(a) ao objetivo {objetivo_id}" if objetivo_id else "desvinculado(a)"
    return _ok(f"✔ {tipo.capitalize()} {id} {acao}.", item)


# --- assinaturas ----------------------------------------------------------------------------


def _linhas_assinaturas(itens: list[dict], cats: dict) -> list[list[object]]:
    return [
        [
            a["id"],
            a["nome"],
            f.brl(a["valor_centavos"]),
            a["periodicidade"],
            cats.get(a.get("categoria_id") or ""),
            "ativa" if a["ativa"] else "inativa",
            ", ".join(a.get("nomes_transacao") or []),
        ]
        for a in itens
    ]


@servidor.tool(annotations=_LEITURA)
async def listar_assinaturas(
    ctx: Context, incluir_inativas: bool = False, formato: Formato = "tabela"
) -> CallToolResult:
    """Lista as assinaturas (streaming, apps, academia…) com valor, periodicidade e categoria,
    e o total mensal equivalente das vigentes."""
    itens = await api(ctx, "GET", "/assinaturas")
    resumo = await api(ctx, "GET", "/assinaturas/resumo")
    if not incluir_inativas:
        itens = [a for a in itens if a["ativa"]]
    cats = await categorias(ctx)
    colunas = [
        "ID",
        "Assinatura",
        "Valor",
        "Periodicidade",
        "Categoria",
        "Situação",
        "Nomes no extrato",
    ]
    md = _md(
        "## Assinaturas",
        f.tabela(colunas, _linhas_assinaturas(itens, cats), formato),
        f"**Total mensal equivalente (vigentes):** {f.brl(resumo['total_mensal_centavos'])}",
    )
    return _ok(md, {"assinaturas": itens, "resumo": resumo})


@servidor.tool(annotations=_LEITURA)
async def listar_candidatos_assinatura(ctx: Context, formato: Formato = "tabela") -> CallToolResult:
    """Cobranças recorrentes detectadas nas transações que ainda não viraram assinatura. Para
    confirmar, chame `criar_assinatura` com os dados do candidato; para descartar,
    `rejeitar_candidato_assinatura` com os `transacao_ids` dele."""
    itens = await api(ctx, "GET", "/assinaturas/candidatos")
    cats = await categorias(ctx)
    linhas = [
        [
            i + 1,
            c["nome"],
            f.brl(c["valor_centavos"]),
            c["periodicidade"],
            cats.get(c.get("categoria_id") or ""),
            c["ocorrencias"],
            f.data(c["data_inicio"]),
            ", ".join(map(str, c["transacao_ids"])),
        ]
        for i, c in enumerate(itens)
    ]
    colunas = [
        "#",
        "Nome",
        "Valor",
        "Periodicidade",
        "Categoria",
        "Cobranças",
        "Desde",
        "Transações",
    ]
    md = _md("## Possíveis assinaturas", f.tabela(colunas, linhas, formato))
    return _ok(md, itens)


@servidor.tool(annotations=_ESCRITA)
async def criar_assinatura(
    ctx: Context,
    nome: Annotated[str, Field(min_length=1, max_length=255)],
    valor: Annotated[float, Field(ge=0, description="Em reais, ex.: 39.90")],
    periodicidade: _PERIODICIDADES,
    categoria: NomeOuId | None = None,
    conta: Annotated[NomeOuId | None, Field(description="Conta/cartão onde é cobrada")] = None,
    data_inicio: date | None = None,
    descricao: str | None = None,
    nomes_transacao: Annotated[
        list[str] | None,
        Field(description="Como a cobrança aparece no extrato; vincula as transações que casam"),
    ] = None,
    detectada_automaticamente: Annotated[
        bool, Field(description="True ao confirmar um candidato de listar_candidatos_assinatura")
    ] = False,
) -> CallToolResult:
    """Cadastra uma assinatura (ou confirma um candidato detectado)."""
    corpo = {
        "nome": nome,
        "valor_centavos": f.reais_para_centavos(valor),
        "periodicidade": periodicidade,
        "categoria_id": await _resolver_categoria(ctx, categoria)
        if categoria is not None
        else None,
        "conta_id": await _resolver_conta(ctx, conta) if conta is not None else None,
        "data_inicio": data_inicio and data_inicio.isoformat(),
        "descricao": descricao,
        "nomes_transacao": nomes_transacao or [],
        "detectada_automaticamente": detectada_automaticamente,
    }
    a = await api(ctx, "POST", "/assinaturas", corpo=corpo)
    return _ok(f"✔ Assinatura **{a['nome']}** criada (id {a['id']}).", a)


@servidor.tool(annotations=_IDEMPOTENTE)
async def atualizar_assinatura(
    ctx: Context,
    assinatura_id: int,
    nome: Annotated[str | None, Field(min_length=1, max_length=255)] = None,
    valor: Annotated[float | None, Field(ge=0, description="Em reais")] = None,
    periodicidade: _PERIODICIDADES | None = None,
    categoria: NomeOuId | None = None,
    data_inicio: date | None = None,
    descricao: str | None = None,
    ativa: Annotated[bool | None, Field(description="False = cancelada")] = None,
    nomes_transacao: Annotated[
        list[str] | None, Field(description="Substitui a lista inteira; re-vincula transações")
    ] = None,
) -> CallToolResult:
    """Altera uma assinatura (só os campos informados). Para cancelar sem apagar o histórico,
    use ativa=false."""
    corpo: dict[str, Any] = {
        "nome": nome,
        "valor_centavos": f.reais_para_centavos(valor) if valor is not None else None,
        "periodicidade": periodicidade,
        "categoria_id": await _resolver_categoria(ctx, categoria)
        if categoria is not None
        else None,
        "data_inicio": data_inicio and data_inicio.isoformat(),
        "descricao": descricao,
        "ativa": ativa,
        "nomes_transacao": nomes_transacao,
    }
    corpo = {k: v for k, v in corpo.items() if v is not None}
    if not corpo:
        raise ToolError("nenhum campo para alterar")
    a = await api(ctx, "PATCH", f"/assinaturas/{assinatura_id}", corpo=corpo)
    return _ok(f"✔ Assinatura **{a['nome']}** atualizada.", a)


@servidor.tool(annotations=_DESTRUTIVA)
async def excluir_assinatura(ctx: Context, assinatura_id: int) -> CallToolResult:
    """Apaga uma assinatura de vez (as transações ficam, só perdem o vínculo). Para só cancelar,
    prefira `atualizar_assinatura` com ativa=false. Confirme com o usuário antes."""
    a = await api(ctx, "GET", f"/assinaturas/{assinatura_id}")
    await api(ctx, "DELETE", f"/assinaturas/{assinatura_id}")
    return _ok(f"✔ Assinatura **{a['nome']}** excluída.", {"excluida": a})


@servidor.tool(annotations=_IDEMPOTENTE)
async def rejeitar_candidato_assinatura(
    ctx: Context, transacao_ids: Annotated[list[int], Field(min_length=1, max_length=200)]
) -> CallToolResult:
    """Descarta um candidato de assinatura: marca as transações dele como "não é assinatura",
    para não serem sugeridas de novo."""
    falhas = []
    for transacao_id in transacao_ids:
        try:
            await api(ctx, "PATCH", f"/transacoes/{transacao_id}", corpo={"nao_e_assinatura": True})
        except ToolError as erro:
            falhas.append({"id": transacao_id, "erro": str(erro)})
    feitas = len(transacao_ids) - len(falhas)
    md = _md(
        f"✔ {feitas} transação(ões) marcada(s) como não-assinatura.",
        f.tabela(["ID", "Erro"], [[x["id"], x["erro"]] for x in falhas]) if falhas else None,
    )
    return _ok(md, {"marcadas": feitas, "falhas": falhas})


# --- orçamentos -----------------------------------------------------------------------------


@servidor.tool(annotations=_LEITURA)
async def listar_orcamentos(
    ctx: Context,
    ano: Annotated[int | None, Field(ge=2000, le=2100, description="Padrão: mês atual")] = None,
    mes: Annotated[int | None, Field(ge=1, le=12)] = None,
    formato: Formato = "tabela",
) -> CallToolResult:
    """Orçamentos do mês por categoria: limite, quanto já foi gasto (ou recebido, nas metas de
    receita), percentual e alerta atingido (50/75/90/100%)."""
    hoje = hoje_sp()
    ano, mes = ano or hoje.year, mes or hoje.month
    consumo = await api(ctx, "GET", "/orcamentos/consumo", params={"ano": ano, "mes": mes})
    cats = await categorias(ctx)
    itens = [i for i in consumo["itens"] if not i["suprimido"]]
    linhas = [
        [
            cats.get(i["categoria_id"], i["categoria_id"]),
            i["tipo"],
            f.brl(i["limite_centavos"]),
            f.brl(i["realizado_centavos"]),
            f"{f.barra(i['percentual'] / 100)} {i['percentual']}%",
            f"⚠ {i['alerta_atingido']}%" if i.get("alerta_atingido") else None,
        ]
        for i in itens
    ]
    colunas = ["Categoria", "Tipo", "Limite", "Realizado", "Uso", "Alerta"]
    md = _md(f"## Orçamentos — {mes:02d}/{ano}", f.tabela(colunas, linhas, formato))
    return _ok(md, consumo)


# --- divisão de contas ----------------------------------------------------------------------


async def _eu(ctx: Context) -> dict:
    return await api(ctx, "GET", "/auth/me")


async def _pessoas(ctx: Context, busca: str | None = None) -> dict[int, dict]:
    """Contrapartes conhecidas (`/pessoas`, com saldo) + usuários da instância que casam com a
    busca. A busca exige ≥2 caracteres e nunca devolve e-mail (ROADMAP: `/usuarios/buscar`)."""
    pessoas = {p["usuario_id"]: p for p in await api(ctx, "GET", "/divisoes-despesa/pessoas")}
    if busca and len(busca.strip()) >= 2:
        for u in await api(ctx, "GET", "/usuarios/buscar", params={"q": busca.strip()}):
            pessoas.setdefault(
                u["id"],
                {
                    "usuario_id": u["id"],
                    "nome": u["nome"],
                    "status": u["status"],
                    "saldo_centavos": 0,
                },
            )
    return pessoas


async def _resolver_pessoa(ctx: Context, valor: NomeOuId, eu: dict) -> int:
    if isinstance(valor, str) and valor.strip().casefold() in {"eu", "mim", "me", "eu mesmo"}:
        return eu["id"]
    pessoas = await _pessoas(ctx, valor if isinstance(valor, str) else None)
    opcoes = {pid: p["nome"] for pid, p in pessoas.items()} | {eu["id"]: eu["nome"]}
    return resolver_nome(valor, opcoes, "pessoa")


def _saldo_texto(nome: str, saldo: int) -> str:
    if saldo > 0:
        return f"**{nome}** te deve {f.brl(saldo)}"
    if saldo < 0:
        return f"Você deve {f.brl(-saldo)} a **{nome}**"
    return f"Você e **{nome}** estão quites"


@servidor.tool(annotations=_LEITURA)
async def listar_pessoas_divisao(
    ctx: Context,
    busca: Annotated[
        str | None, Field(description="Nome (≥2 letras) p/ achar outros usuários")
    ] = None,
    formato: Formato = "tabela",
) -> CallToolResult:
    """Pessoas com quem você divide despesas (e o saldo com cada uma). Com `busca`, inclui
    outros usuários da instância com esse nome — útil antes de `criar_divisao`."""
    pessoas = list((await _pessoas(ctx, busca)).values())
    if busca:
        termo = busca.casefold()
        pessoas = [p for p in pessoas if termo in p["nome"].casefold()]
    linhas = [
        [
            p["usuario_id"],
            p["nome"],
            "só divisão" if p.get("status") == "so_divisao" else "usuário",
            f.brl(p.get("saldo_centavos", 0)),
        ]
        for p in pessoas
    ]
    md = _md(
        "## Pessoas",
        f.tabela(["ID", "Nome", "Conta", "Saldo (+ te deve)"], linhas, formato),
    )
    return _ok(md, pessoas)


@servidor.tool(annotations=_LEITURA)
async def saldos_divisao(
    ctx: Context,
    pessoa: Annotated[NomeOuId | None, Field(description="Id ou nome; vazio = todas")] = None,
    formato: Formato = "tabela",
) -> CallToolResult:
    """Quanto cada pessoa te deve (ou você deve a ela) na divisão de contas — no geral ou com
    uma pessoa específica, junto das despesas em aberto entre vocês."""
    otimizado = (await api(ctx, "GET", "/configuracao-sistema"))["otimizar_transacoes_divisao"]
    nota = (
        "_Saldos otimizados: as dívidas entre várias pessoas são simplificadas no grupo._"
        if otimizado
        else None
    )
    if pessoa is None:
        resumo = await api(ctx, "GET", "/divisoes-despesa/resumo")
        pessoas = [p for p in (await _pessoas(ctx)).values() if p["saldo_centavos"]]
        md = _md(
            "## Saldos na divisão de contas",
            f"A receber: **{f.brl(resumo['saldo_a_receber_centavos'])}** "
            f"({resumo['pessoas_a_receber']} pessoa(s)) · A pagar: "
            f"**{f.brl(resumo['saldo_a_pagar_centavos'])}** ({resumo['pessoas_a_pagar']} pessoa(s))"
            f" · Líquido: **{f.brl(resumo['saldo_total_centavos'])}**",
            "\n".join(f"- {_saldo_texto(p['nome'], p['saldo_centavos'])}" for p in pessoas)
            or "_Ninguém deve nada a ninguém._",
            nota,
        )
        return _ok(md, {"resumo": resumo, "pessoas": pessoas, "otimizado": otimizado})

    eu = await _eu(ctx)
    pid = await _resolver_pessoa(ctx, pessoa, eu)
    alvo = (await _pessoas(ctx)).get(pid) or {
        "usuario_id": pid,
        "nome": str(pessoa),
        "saldo_centavos": 0,
    }
    abertas = [
        d
        for d in await api(ctx, "GET", "/divisoes-despesa", params={"escopo": "todas"})
        if not d["quitada"]
        and (
            d["pago_por_usuario_id"] == pid
            or any(p["usuario_id"] == pid for p in d["participantes"])
        )
    ]
    md = _md(
        f"## Divisão com {alvo['nome']}",
        _saldo_texto(alvo["nome"], alvo["saldo_centavos"]) + ".",
        "### Despesas em aberto\n\n" + f.tabela(*_tabela_divisoes(abertas), formato),
        nota,
    )
    return _ok(md, {"pessoa": alvo, "divisoes_abertas": abertas, "otimizado": otimizado})


def _tabela_divisoes(itens: list[dict]) -> tuple[list[str], list[list[object]]]:
    colunas = [
        "ID",
        "Data",
        "Descrição",
        "Total",
        "Pago por",
        "Participantes",
        "Meu saldo",
        "Situação",
    ]
    linhas = []
    for d in itens:
        nomes = {p["usuario_id"]: p["nome"] for p in d["participantes"]}
        linhas.append(
            [
                d["id"],
                f.data(d["criado_em"]),
                d.get("descricao"),
                f.brl(d["valor_total_centavos"]),
                nomes.get(d["pago_por_usuario_id"], d["pago_por_usuario_id"]),
                ", ".join(f"{p['nome']} {f.brl(p['valor_centavos'])}" for p in d["participantes"]),
                f.brl(d["meu_saldo_centavos"]),
                "quitada" if d["quitada"] else ("arquivada" if d["arquivada"] else "em aberto"),
            ]
        )
    return colunas, linhas


@servidor.tool(annotations=_LEITURA)
async def listar_divisoes(
    ctx: Context,
    escopo: Annotated[
        Literal["todas", "minhas", "comigo", "arquivadas"],
        Field(description="minhas = criadas por você; comigo = criadas por outros com você"),
    ] = "todas",
    apenas_abertas: bool = False,
    limite: Annotated[int, Field(ge=1, le=200)] = 50,
    formato: Formato = "tabela",
) -> CallToolResult:
    """Lista as despesas divididas, com quem pagou, a parte de cada um e o seu saldo em cada."""
    itens = await api(ctx, "GET", "/divisoes-despesa", params={"escopo": escopo})
    if apenas_abertas:
        itens = [d for d in itens if not d["quitada"]]
    md = _md(
        "## Divisões de despesa",
        f.tabela(*_tabela_divisoes(itens[:limite]), formato),
        f.paginacao(min(len(itens), limite), len(itens), 0),
    )
    return _ok(md, itens[:limite])


@servidor.tool(annotations=_ESCRITA)
async def criar_divisao(
    ctx: Context,
    descricao: Annotated[str, Field(min_length=1, max_length=255)],
    valor: Annotated[float, Field(gt=0, description="Valor total em reais")],
    participantes: Annotated[
        list[NomeOuId],
        Field(
            min_length=1,
            description="Com quem dividir (ids ou nomes). Em 'igualmente', quem pagou entra "
            "automaticamente; em 'integral', exatamente 1 pessoa: quem deve tudo.",
        ),
    ],
    pago_por: Annotated[
        NomeOuId, Field(description="Quem pagou: 'eu' (padrão), id ou nome")
    ] = "eu",
    modo: Literal["igualmente", "integral"] = "igualmente",
    categoria: NomeOuId | None = None,
) -> CallToolResult:
    """Cria uma despesa dividida (rachar uma conta). 'igualmente' divide em partes iguais entre
    quem pagou e os participantes; 'integral' faz um participante dever o valor inteiro."""
    eu = await _eu(ctx)
    pagador = await _resolver_pessoa(ctx, pago_por, eu)
    ids = [await _resolver_pessoa(ctx, p, eu) for p in participantes]
    corpo = {
        "descricao": descricao,
        "valor_total_centavos": f.reais_para_centavos(valor),
        "pago_por_usuario_id": pagador,
        "modo_divisao": modo,
        "participantes": ids,
        "categoria_id": await _resolver_categoria(ctx, categoria)
        if categoria is not None
        else None,
    }
    d = await api(ctx, "POST", "/divisoes-despesa", corpo=corpo)
    partes = "\n".join(f"- {p['nome']}: {f.brl(p['valor_centavos'])}" for p in d["participantes"])
    return _ok(
        _md(
            f"✔ Divisão **{descricao}** criada (id {d['id']}) — "
            f"{f.brl(d['valor_total_centavos'])}.",
            partes,
        ),
        d,
    )


@servidor.tool(annotations=_IDEMPOTENTE)
async def quitar_divisao(ctx: Context, divisao_id: int) -> CallToolResult:
    """Marca uma despesa dividida como quitada (acertada) — ela sai dos saldos."""
    d = await api(ctx, "POST", f"/divisoes-despesa/{divisao_id}/quitar")
    return _ok(f"✔ Divisão **{d.get('descricao') or d['id']}** quitada.", d)


@servidor.tool(annotations=_IDEMPOTENTE)
async def reabrir_divisao(ctx: Context, divisao_id: int) -> CallToolResult:
    """Desfaz a quitação de uma despesa dividida — ela volta a contar nos saldos."""
    d = await api(ctx, "POST", f"/divisoes-despesa/{divisao_id}/reabrir")
    return _ok(f"✔ Divisão **{d.get('descricao') or d['id']}** reaberta.", d)


@servidor.tool(annotations=_DESTRUTIVA)
async def excluir_divisao(ctx: Context, divisao_id: int) -> CallToolResult:
    """Apaga uma despesa dividida (só quem a criou pode). Confirme com o usuário antes; para
    registrar que foi paga, use `quitar_divisao`."""
    d = await api(ctx, "GET", f"/divisoes-despesa/{divisao_id}")
    await api(ctx, "DELETE", f"/divisoes-despesa/{divisao_id}")
    return _ok(f"✔ Divisão **{d.get('descricao') or divisao_id}** excluída.", {"excluida": d})


# --- visão geral, investimentos e renda -----------------------------------------------------


@servidor.tool(annotations=_LEITURA)
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
    md = _md(
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
    return _ok(md, r)


@servidor.tool(annotations=_LEITURA)
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
    md = _md(
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
    return _ok(md, {"totais": t, "alocacao": resumo["alocacao"], "visao_geral": visao})


@servidor.tool(annotations=_LEITURA)
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
    md = _md("## Carteira", f.tabela(colunas, linhas, formato))
    return _ok(md, posicoes)


@servidor.tool(annotations=_LEITURA)
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
    md = _md(
        "## Fontes de renda",
        f.tabela(
            ["ID", "Nome", "Tipo", "Valor estimado", "Recorrência", "Origem"], linhas, formato
        ),
    )
    return _ok(md, itens)


# --- gráficos -------------------------------------------------------------------------------

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
    return graficos.HTML_APP


@servidor.tool(annotations=_LEITURA, meta={"ui": {"resourceUri": _URI_APP_GRAFICO}})
async def grafico(
    ctx: Context,
    tipo: Annotated[
        Literal[
            "gastos_por_categoria",
            "receitas_vs_despesas",
            "saldo_contas",
            "evolucao_investimentos",
            "orcamento_mes",
            "faturas_cartao",
        ],
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
    hoje = hoje_sp()
    cats = await categorias(ctx)

    if tipo == "gastos_por_categoria":
        ini, fi = inicio or hoje.replace(day=1), fim or hoje
        r = await api(
            ctx, "GET", "/dashboard", params={"inicio": ini.isoformat(), "fim": fi.isoformat()}
        )
        itens = graficos.dobrar_em_outras(
            [
                (cats.get(g["categoria_id"] or "", "Sem categoria"), g["total_centavos"] / 100)
                for g in r["gasto_por_categoria"]
            ]
        )
        spec = graficos.barras_horizontais(
            f"Gastos por categoria — {f.data(ini)} a {f.data(fi)}", itens
        )
        tabela = (["Categoria", "Total"], [[n, f.brl(round(v * 100))] for n, v in itens])
    elif tipo == "receitas_vs_despesas":
        fi = fim or hoje
        ini = inicio or (fi.replace(day=1) - timedelta(days=150)).replace(day=1)
        params = {"inicio": ini.isoformat(), "fim": fi.isoformat(), "granularidade": "mensal"}
        buckets = (await api(ctx, "GET", "/dashboard/series", params=params))["buckets"]
        dados = [
            {"periodo": _mes_rotulo(b["inicio"]), "serie": s, "valor": b[k] / 100}
            for b in buckets
            for s, k in (("Entradas", "entradas_centavos"), ("Saídas", "saidas_centavos"))
        ]
        spec = graficos.barras_agrupadas("Entradas × saídas por mês", dados)
        tabela = (
            ["Mês", "Entradas", "Saídas", "Resultado"],
            [
                [
                    _mes_rotulo(b["inicio"]),
                    f.brl(b["entradas_centavos"]),
                    f.brl(b["saidas_centavos"]),
                    f.brl(b["resultado_centavos"]),
                ]
                for b in buckets
            ],
        )
    elif tipo == "saldo_contas":
        dias = min(max((hoje - inicio).days + 1, 2), 365) if inicio else 30
        series = await api(ctx, "GET", "/contas/saldos-diarios", params={"dias": dias})
        cts = await contas(ctx)
        dados = [
            {
                "data": p["data"],
                "serie": nome_conta(cts[s["conta_id"]]),
                "valor": p["saldo_centavos"] / 100,
            }
            for s in series
            if s["conta_id"] in cts
            for p in s["pontos"]
        ]
        spec = graficos.linhas(f"Saldo das contas — últimos {dias} dias", dados)
        tabela = (
            ["Conta", "Início", "Hoje", "Variação"],
            [
                [
                    nome_conta(cts[s["conta_id"]]),
                    f.brl(s["pontos"][0]["saldo_centavos"]),
                    f.brl(s["pontos"][-1]["saldo_centavos"]),
                    f.brl(s["pontos"][-1]["saldo_centavos"] - s["pontos"][0]["saldo_centavos"]),
                ]
                for s in series
                if s["pontos"] and s["conta_id"] in cts
            ],
        )
    elif tipo == "evolucao_investimentos":
        fi = fim or hoje
        ini = inicio or fi - timedelta(days=365)
        serie = await api(
            ctx,
            "GET",
            "/investimentos/serie",
            params={"inicio": ini.isoformat(), "fim": fi.isoformat()},
        )
        pontos = serie["pontos"]
        dados = [
            {"data": p["data"], "serie": s, "valor": p[k] / 100}
            for p in pontos
            for s, k in (("Patrimônio", "valor_centavos"), ("Investido", "investido_centavos"))
        ]
        spec = graficos.linhas("Evolução dos investimentos", dados)
        tabela = (
            ["", "Início", "Fim"],
            [
                [s, f.brl(pontos[0][k]), f.brl(pontos[-1][k])]
                for s, k in (("Patrimônio", "valor_centavos"), ("Investido", "investido_centavos"))
            ]
            if pontos
            else [],
        )
    elif tipo == "orcamento_mes":
        ano, mes = ano or hoje.year, mes or hoje.month
        consumo = await api(ctx, "GET", "/orcamentos/consumo", params={"ano": ano, "mes": mes})
        itens = [
            {
                "categoria": cats.get(i["categoria_id"], i["categoria_id"]),
                "realizado": i["realizado_centavos"] / 100,
                "limite": i["limite_centavos"] / 100,
                "percentual": i["percentual"],
            }
            for i in consumo["itens"]
            if not i["suprimido"] and i["tipo"] == "despesa"
        ]
        spec = graficos.orcamento(f"Orçamentos de despesa — {mes:02d}/{ano}", itens)
        tabela = (
            ["Categoria", "Realizado", "Limite", "Uso"],
            [
                [
                    i["categoria"],
                    f.brl(round(i["realizado"] * 100)),
                    f.brl(round(i["limite"] * 100)),
                    f"{i['percentual']}%",
                ]
                for i in itens
            ],
        )
    else:  # faturas_cartao
        if cartao is None:
            raise ToolError("informe o `cartao` (id ou nome) para faturas_cartao")
        cartao_id = await _resolver_conta(ctx, cartao)
        buckets = (
            await api(ctx, "GET", f"/contas/{cartao_id}/faturas-resumo", params={"limite": 6})
        )["buckets"]
        totais: dict[str, int] = defaultdict(int)
        for b in buckets:
            for g in b["por_categoria"]:
                totais[g["categoria_id"] or ""] += g["total_centavos"]
        principais = [cid for cid, _ in sorted(totais.items(), key=lambda kv: -kv[1])][
            : graficos.MAX_SERIES - 1
        ]
        rotulos = {
            **cats,
            AJUSTE_CATEGORIA_ID: "Encargos e ajustes",
        }  # total − compras (juros, IOF…)
        nome = {cid: rotulos.get(cid, "Sem categoria") for cid in principais}
        series = [nome[c] for c in principais] + (
            ["Outras"] if len(totais) > len(principais) else []
        )
        dados = []
        for b in buckets:
            por_serie: dict[str, int] = defaultdict(int)
            for g in b["por_categoria"]:
                por_serie[nome.get(g["categoria_id"] or "", "Outras")] += g["total_centavos"]
            dados += [
                {
                    "periodo": f.data(b["due_date"]),
                    "serie": s,
                    "valor": por_serie[s] / 100,
                    "ordem": i,
                }
                for i, s in enumerate(series)
                if por_serie.get(s)
            ]
        spec = graficos.empilhadas(
            f"Faturas — {nome_conta((await contas(ctx))[cartao_id])}", dados, series
        )
        tabela = (
            ["Vencimento", "Total"],
            [[f.data(b["due_date"]), f.brl(b["total_centavos"])] for b in buckets],
        )

    imagem = await anyio.to_thread.run_sync(graficos.png, spec)  # CPU: fora do event loop
    md = _md(f"## {spec['title']}", f.tabela(*tabela))
    return CallToolResult(
        content=[
            TextContent(text=md),
            ImageContent(data=base64.b64encode(imagem).decode(), mime_type="image/png"),
        ],
        structured_content={"tipo": tipo, "spec": spec},
    )


# --- prompts (roteiros prontos que encadeiam as tools) ---------------------------------------


@servidor.prompt(title="Revisar transações pendentes")
def revisar_pendentes() -> str:
    """Passa pela fila de revisão sugerindo categorias e marcando como revisadas."""
    return (
        "Revise minhas transações pendentes no mango. 1) Chame `listar_transacoes` com "
        "pendente_revisao=true (limite 50). 2) Agrupe as parecidas (mesmo estabelecimento) e, para "
        "cada grupo, sugira a categoria — use `listar_categorias` para achar os nomes válidos. "
        "3) Mostre a proposta em tabela e ESPERE minha confirmação. 4) Só então aplique com "
        "`atualizar_transacoes` (categoria + revisada=true), um grupo por chamada, e reporte as "
        "falhas. Se houver mais páginas, pergunte se continuo."
    )


@servidor.prompt(title="Resumo do mês")
def resumo_do_mes(mes: str = "") -> str:
    """Panorama de um mês (padrão: o atual): resultado, categorias, orçamentos e faturas."""
    alvo = f"do mês {mes}" if mes else "do mês atual"
    return (
        f"Monte um resumo financeiro {alvo} no mango: `resumo_financeiro` (entradas, saídas, "
        "resultado, categorias), `listar_orcamentos` (destaque os acima de 90%), `listar_cartoes` "
        "(fatura atual e vencimento) e `grafico` tipo gastos_por_categoria. Termine com 3 "
        "observações objetivas — sem conselhos genéricos."
    )


@servidor.prompt(title="Acerto de contas")
def acerto_de_contas(pessoa: str = "") -> str:
    """Quem deve quanto a quem na divisão de contas, com as despesas em aberto."""
    com = f"com {pessoa}" if pessoa else "com cada pessoa"
    return (
        f"Mostre meu acerto de contas {com} no mango usando `saldos_divisao`"
        + (f" com pessoa='{pessoa}'" if pessoa else "")
        + ". Liste as despesas em aberto e diga claramente quem deve pagar quanto a quem. Se eu "
        "confirmar que o acerto foi feito, marque as despesas com `quitar_divisao`."
    )
