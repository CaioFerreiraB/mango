"""Tools de transações: listar/buscar/detalhar e editar em lote (docs/mcp.md §1.1)."""

from datetime import date, timedelta
from typing import Annotated, Any, Literal

from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import CallToolResult
from pydantic import Field

from app.mcp import formato as f
from app.mcp.api import api, categorias, contas, nome_conta
from app.mcp.servidor import (
    ESCRITA,
    LEITURA,
    Formato,
    NomeOuId,
    juntar,
    ok,
    resolver_categoria,
    resolver_conta,
    servidor,
)
from app.services.periodo import hoje_sp

# --- transações -----------------------------------------------------------------------------


def _descricao(t: dict) -> str:
    return t.get("descricao_usuario") or t.get("merchant_nome") or t.get("description") or "—"


def valor_com_sinal(t: dict) -> int:
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


def linhas_transacoes(itens: list[dict], cats: dict, cts: dict) -> list[list[object]]:
    return [
        [
            t["id"],
            f.data(t["date"]),
            _descricao(t),
            nome_conta(cts[t["conta_id"]]) if t["conta_id"] in cts else t["conta_id"],
            cats.get(t.get("categoria_efetiva_id") or ""),
            f.brl(valor_com_sinal(t)),
            _situacao(t),
        ]
        for t in itens
    ]


COLUNAS_TRANSACAO = ["ID", "Data", "Descrição", "Conta", "Categoria", "Valor", "Situação"]


async def _tabela_transacoes(
    ctx: Context, params: dict, formato: f.Formato, titulo: str
) -> CallToolResult:
    pagina = await api(ctx, "GET", "/transacoes", params=params)
    itens, total = pagina["items"], pagina["total"]
    cats, cts = await categorias(ctx), await contas(ctx)
    despesas = sum(v for t in itens if (v := valor_com_sinal(t)) < 0)
    receitas = sum(v for t in itens if (v := valor_com_sinal(t)) > 0)
    md = juntar(
        f"## {titulo}",
        f.tabela(COLUNAS_TRANSACAO, linhas_transacoes(itens, cats, cts), formato),
        f"Nesta página: despesas **{f.brl(despesas)}** · receitas **{f.brl(receitas)}**"
        if itens
        else None,
        f.paginacao(len(itens), total, params.get("offset") or 0),
    )
    return ok(md, {"total": total, "offset": params.get("offset") or 0, "transacoes": itens})


@servidor.tool(annotations=LEITURA)
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
    # lizard forgives — a assinatura É o schema da tool: parâmetros planos são o que os agentes
    # preenchem melhor (um objeto aninhado de filtros piora o acerto das chamadas).
    params = {
        "inicio": inicio and inicio.isoformat(),
        "fim": fim and fim.isoformat(),
        "conta_id": await resolver_conta(ctx, conta) if conta is not None else None,
        "categoria_id": await resolver_categoria(ctx, categoria) if categoria is not None else None,
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


@servidor.tool(annotations=LEITURA)
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


@servidor.tool(annotations=LEITURA)
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
        ("Valor", f.brl(valor_com_sinal(t))),
        ("Conta", nome_conta(cts[t["conta_id"]]) if t["conta_id"] in cts else t["conta_id"]),
        ("Categoria", f"{cats.get(t.get('categoria_efetiva_id') or '', '—')} ({origem})"),
        ("Situação", _situacao(t)),
        ("Fatura", t.get("bill_id")),
        ("Assinatura", t.get("assinatura_id")),
        ("Observações", t.get("observacoes")),
        ("Status no banco", "pendente" if t.get("status") == "PENDING" else "lançada"),
    ]
    md = juntar(f"## Transação #{t['id']}", "\n".join(f"- **{k}:** {v or '—'}" for k, v in campos))
    return ok(md, t)


@servidor.tool(annotations=ESCRITA)
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
    # lizard forgives — a assinatura É o schema da tool: parâmetros planos são o que os agentes
    # preenchem melhor (um objeto aninhado de filtros piora o acerto das chamadas).
    if assinatura_id is not None and desvincular_assinatura:
        raise ToolError("informe assinatura_id OU desvincular_assinatura, não os dois")
    if categoria is not None and restaurar_categoria:
        raise ToolError("informe categoria OU restaurar_categoria, não os dois")
    payload: dict[str, Any] = {
        chave: valor
        for chave, valor in {
            "revisada": revisada,
            "nao_e_assinatura": nao_e_assinatura,
            "eh_transferencia": eh_transferencia,
            "descricao_usuario": descricao,
            "observacoes": observacoes,
        }.items()
        if valor is not None
    }
    # Os três vínculos abaixo têm "desligar" explícito: `None` no PATCH significa desvincular.
    if categoria is not None or restaurar_categoria:
        payload["categoria_override_id"] = (
            await resolver_categoria(ctx, categoria) if categoria is not None else None
        )
        payload["categoria_ajustada_usuario"] = categoria is not None
    if assinatura_id is not None or desvincular_assinatura:
        payload["assinatura_id"] = assinatura_id
    if provento_id is not None or desvincular_provento:
        payload["investimento_transacao_id"] = provento_id
    if not payload:
        raise ToolError("nenhum campo para alterar")

    feitas, falhas = await patch_em_lote(ctx, ids, payload)
    parcelas = sum(t.get("parcelas_atualizadas", 0) for t in feitas)
    extra = (
        f" Outras {parcelas} parcela(s) da mesma compra foram recategorizadas." if parcelas else ""
    )
    md = juntar(
        f"✔ {len(feitas)} de {len(feitas) + len(falhas)} transação(ões) atualizada(s).{extra}",
        tabela_falhas(falhas),
    )
    return ok(md, {"atualizadas": feitas, "falhas": falhas, "parcelas_atualizadas": parcelas})


async def patch_em_lote(
    ctx: Context, ids: list[int], payload: dict
) -> tuple[list[dict], list[dict]]:
    """PATCH de `payload` em cada transação (sem repetir, na ordem dada). Uma falha não para as
    outras: devolve (atualizadas, [{id, erro}])."""
    feitas, falhas = [], []
    for transacao_id in dict.fromkeys(ids):
        try:
            feitas.append(await api(ctx, "PATCH", f"/transacoes/{transacao_id}", corpo=payload))
        except ToolError as erro:
            falhas.append({"id": transacao_id, "erro": str(erro)})
    return feitas, falhas


def tabela_falhas(falhas: list[dict]) -> str | None:
    return f.tabela(["ID", "Erro"], [[x["id"], x["erro"]] for x in falhas]) if falhas else None


@servidor.tool(annotations=LEITURA)
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
    md = juntar("## Categorias", f.tabela(["ID", "Categoria", "Pai", "Origem"], linhas, formato))
    return ok(md, itens)
