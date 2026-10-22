"""Tools da divisão de contas: pessoas, saldos, criar/quitar/excluir (docs/mcp.md §1.1)."""

from typing import Annotated, Literal

from mcp.server.mcpserver import Context
from mcp_types import CallToolResult
from pydantic import Field

from app.mcp import formato as f
from app.mcp.api import api, resolver_nome
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
    servidor,
)

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
    # Id vai direto: quem ainda não dividiu nada com você não está em `/pessoas`, e a existência
    # do usuário já é validada pelo service da divisão.
    if isinstance(valor, int) or valor.strip().isdigit():
        return int(valor)
    pessoas = await _pessoas(ctx, valor if isinstance(valor, str) else None)
    opcoes = {pid: p["nome"] for pid, p in pessoas.items()} | {eu["id"]: eu["nome"]}
    return resolver_nome(valor, opcoes, "pessoa")


def _saldo_texto(nome: str, saldo: int) -> str:
    if saldo > 0:
        return f"**{nome}** te deve {f.brl(saldo)}"
    if saldo < 0:
        return f"Você deve {f.brl(-saldo)} a **{nome}**"
    return f"Você e **{nome}** estão quites"


@servidor.tool(annotations=LEITURA)
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
    md = juntar(
        "## Pessoas",
        f.tabela(["ID", "Nome", "Conta", "Saldo (+ te deve)"], linhas, formato),
    )
    return ok(md, pessoas)


@servidor.tool(annotations=LEITURA)
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
        md = juntar(
            "## Saldos na divisão de contas",
            f"A receber: **{f.brl(resumo['saldo_a_receber_centavos'])}** "
            f"({resumo['pessoas_a_receber']} pessoa(s)) · A pagar: "
            f"**{f.brl(resumo['saldo_a_pagar_centavos'])}** ({resumo['pessoas_a_pagar']} pessoa(s))"
            f" · Líquido: **{f.brl(resumo['saldo_total_centavos'])}**",
            "\n".join(f"- {_saldo_texto(p['nome'], p['saldo_centavos'])}" for p in pessoas)
            or "_Ninguém deve nada a ninguém._",
            nota,
        )
        return ok(md, {"resumo": resumo, "pessoas": pessoas, "otimizado": otimizado})

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
    md = juntar(
        f"## Divisão com {alvo['nome']}",
        _saldo_texto(alvo["nome"], alvo["saldo_centavos"]) + ".",
        "### Despesas em aberto\n\n" + f.tabela(*_tabela_divisoes(abertas), formato),
        nota,
    )
    return ok(md, {"pessoa": alvo, "divisoes_abertas": abertas, "otimizado": otimizado})


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


@servidor.tool(annotations=LEITURA)
async def listar_divisoes(
    ctx: Context,
    escopo: Annotated[
        Literal["todas", "minhas", "comigo", "arquivadas"],
        Field(description="minhas = criadas por você; comigo = criadas por outros com você"),
    ] = "todas",
    apenas_abertas: bool = False,
    limite: Annotated[int, Field(ge=1, le=200)] = 50,
    offset: Annotated[int, Field(ge=0)] = 0,
    formato: Formato = "tabela",
) -> CallToolResult:
    """Lista as despesas divididas, com quem pagou, a parte de cada um e o seu saldo em cada."""
    itens = await api(ctx, "GET", "/divisoes-despesa", params={"escopo": escopo})
    if apenas_abertas:
        itens = [d for d in itens if not d["quitada"]]
    pagina = itens[offset : offset + limite]
    md = juntar(
        "## Divisões de despesa",
        f.tabela(*_tabela_divisoes(pagina), formato),
        f.paginacao(len(pagina), len(itens), offset),
    )
    return ok(md, pagina)


@servidor.tool(annotations=ESCRITA)
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
        "categoria_id": await resolver_categoria(ctx, categoria) if categoria is not None else None,
    }
    d = await api(ctx, "POST", "/divisoes-despesa", corpo=corpo)
    partes = "\n".join(f"- {p['nome']}: {f.brl(p['valor_centavos'])}" for p in d["participantes"])
    return ok(
        juntar(
            f"✔ Divisão **{descricao}** criada (id {d['id']}) — "
            f"{f.brl(d['valor_total_centavos'])}.",
            partes,
        ),
        d,
    )


@servidor.tool(annotations=IDEMPOTENTE)
async def quitar_divisao(ctx: Context, divisao_id: int) -> CallToolResult:
    """Marca uma despesa dividida como quitada (acertada) — ela sai dos saldos."""
    d = await api(ctx, "POST", f"/divisoes-despesa/{divisao_id}/quitar")
    return ok(f"✔ Divisão **{d.get('descricao') or d['id']}** quitada.", d)


@servidor.tool(annotations=IDEMPOTENTE)
async def reabrir_divisao(ctx: Context, divisao_id: int) -> CallToolResult:
    """Desfaz a quitação de uma despesa dividida — ela volta a contar nos saldos."""
    d = await api(ctx, "POST", f"/divisoes-despesa/{divisao_id}/reabrir")
    return ok(f"✔ Divisão **{d.get('descricao') or d['id']}** reaberta.", d)


@servidor.tool(annotations=DESTRUTIVA)
async def excluir_divisao(ctx: Context, divisao_id: int) -> CallToolResult:
    """Apaga uma despesa dividida (só quem a criou pode). Confirme com o usuário antes; para
    registrar que foi paga, use `quitar_divisao`."""
    d = await api(ctx, "GET", f"/divisoes-despesa/{divisao_id}")
    await api(ctx, "DELETE", f"/divisoes-despesa/{divisao_id}")
    return ok(f"✔ Divisão **{d.get('descricao') or divisao_id}** excluída.", {"excluida": d})
