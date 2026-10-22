"""Tools de assinaturas e orçamentos (docs/mcp.md §1.1)."""

from datetime import date
from typing import Annotated, Any, Literal

from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import CallToolResult
from pydantic import Field

from app.mcp import formato as f
from app.mcp.api import api, categorias
from app.mcp.servidor import (
    DESTRUTIVA,
    ESCRITA,
    IDEMPOTENTE,
    LEITURA,
    Formato,
    NomeOuId,
    juntar,
    ok,
    resolver_categoria,
    resolver_conta,
    servidor,
)
from app.mcp.tools.transacoes import patch_em_lote, tabela_falhas
from app.services.periodo import hoje_sp

_PERIODICIDADES = Literal["mensal", "trimestral", "semestral", "anual", "irregular"]


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


@servidor.tool(annotations=LEITURA)
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
    md = juntar(
        "## Assinaturas",
        f.tabela(colunas, _linhas_assinaturas(itens, cats), formato),
        f"**Total mensal equivalente (vigentes):** {f.brl(resumo['total_mensal_centavos'])}",
    )
    return ok(md, {"assinaturas": itens, "resumo": resumo})


@servidor.tool(annotations=LEITURA)
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
    md = juntar("## Possíveis assinaturas", f.tabela(colunas, linhas, formato))
    return ok(md, itens)


@servidor.tool(annotations=ESCRITA)
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
    # lizard forgives — a assinatura É o schema da tool: parâmetros planos são o que os agentes
    # preenchem melhor (um objeto aninhado de filtros piora o acerto das chamadas).
    corpo = {
        "nome": nome,
        "valor_centavos": f.reais_para_centavos(valor),
        "periodicidade": periodicidade,
        "categoria_id": await resolver_categoria(ctx, categoria) if categoria is not None else None,
        "conta_id": await resolver_conta(ctx, conta) if conta is not None else None,
        "data_inicio": data_inicio and data_inicio.isoformat(),
        "descricao": descricao,
        "nomes_transacao": nomes_transacao or [],
        "detectada_automaticamente": detectada_automaticamente,
    }
    a = await api(ctx, "POST", "/assinaturas", corpo=corpo)
    return ok(f"✔ Assinatura **{a['nome']}** criada (id {a['id']}).", a)


@servidor.tool(annotations=IDEMPOTENTE)
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
    # lizard forgives — a assinatura É o schema da tool: parâmetros planos são o que os agentes
    # preenchem melhor (um objeto aninhado de filtros piora o acerto das chamadas).
    corpo: dict[str, Any] = {
        "nome": nome,
        "valor_centavos": f.reais_para_centavos(valor) if valor is not None else None,
        "periodicidade": periodicidade,
        "categoria_id": await resolver_categoria(ctx, categoria) if categoria is not None else None,
        "data_inicio": data_inicio and data_inicio.isoformat(),
        "descricao": descricao,
        "ativa": ativa,
        "nomes_transacao": nomes_transacao,
    }
    corpo = {k: v for k, v in corpo.items() if v is not None}
    if not corpo:
        raise ToolError("nenhum campo para alterar")
    a = await api(ctx, "PATCH", f"/assinaturas/{assinatura_id}", corpo=corpo)
    return ok(f"✔ Assinatura **{a['nome']}** atualizada.", a)


@servidor.tool(annotations=DESTRUTIVA)
async def excluir_assinatura(ctx: Context, assinatura_id: int) -> CallToolResult:
    """Apaga uma assinatura de vez (as transações ficam, só perdem o vínculo). Para só cancelar,
    prefira `atualizar_assinatura` com ativa=false. Confirme com o usuário antes."""
    a = await api(ctx, "GET", f"/assinaturas/{assinatura_id}")
    await api(ctx, "DELETE", f"/assinaturas/{assinatura_id}")
    return ok(f"✔ Assinatura **{a['nome']}** excluída.", {"excluida": a})


@servidor.tool(annotations=IDEMPOTENTE)
async def rejeitar_candidato_assinatura(
    ctx: Context, transacao_ids: Annotated[list[int], Field(min_length=1, max_length=200)]
) -> CallToolResult:
    """Descarta um candidato de assinatura: marca as transações dele como "não é assinatura",
    para não serem sugeridas de novo."""
    marcadas, falhas = await patch_em_lote(ctx, transacao_ids, {"nao_e_assinatura": True})
    md = juntar(
        f"✔ {len(marcadas)} transação(ões) marcada(s) como não-assinatura.", tabela_falhas(falhas)
    )
    return ok(md, {"marcadas": len(marcadas), "falhas": falhas})


# --- orçamentos -----------------------------------------------------------------------------


@servidor.tool(annotations=LEITURA)
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
    md = juntar(f"## Orçamentos — {mes:02d}/{ano}", f.tabela(colunas, linhas, formato))
    return ok(md, consumo)
