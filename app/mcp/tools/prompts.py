"""Prompts MCP: roteiros prontos que encadeiam as tools (docs/mcp.md §1.1)."""

from app.mcp.servidor import servidor

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
