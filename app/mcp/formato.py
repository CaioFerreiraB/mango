"""Formatação das respostas do MCP (docs/mcp.md §3.3): markdown legível em qualquer cliente.

Dinheiro em pt-BR (`R$ 1.234,56`), datas `dd/mm/aaaa` no fuso SP e tabelas markdown — ou bullets
(`formato="lista"`) para canais que não renderizam tabela (Telegram, WhatsApp). Funções puras;
testes em `tests/test_mcp_formato.py`.
"""

from datetime import date, datetime
from typing import Literal

from app.services.periodo import SP

Formato = Literal["tabela", "lista"]


def brl(centavos: int | None) -> str:
    if centavos is None:
        return "—"
    sinal = "-" if centavos < 0 else ""
    inteiro, cents = divmod(abs(centavos), 100)
    return f"{sinal}R$ {inteiro:,}".replace(",", ".") + f",{cents:02d}"


def reais_para_centavos(valor: float) -> int:
    """Valor em reais vindo do agente → centavos. `round` antes do int: 39.9*100 = 3989.99…"""
    return int(round(valor * 100))


def pct(valor: float | None, casas: int = 1) -> str:
    if valor is None:
        return "—"
    return f"{valor:.{casas}f}%".replace(".", ",")


def data(valor: str | date | datetime | None) -> str:
    """ISO (data ou datetime, com ou sem fuso) → `dd/mm/aaaa`. Datetime vira o dia civil em SP:
    uma compra às 23h de 31/12 em SP chega como 02h de 01/01 em UTC."""
    if valor is None:
        return "—"
    if isinstance(valor, str):
        valor = datetime.fromisoformat(valor) if "T" in valor else date.fromisoformat(valor)
    if isinstance(valor, datetime):
        valor = valor.astimezone(SP).date() if valor.tzinfo else valor.date()
    return valor.strftime("%d/%m/%Y")


def barra(fracao: float, largura: int = 10) -> str:
    """Barra de progresso em texto (`▓▓▓░░░░░░░`) — funciona até em chat sem markdown."""
    cheios = round(max(0.0, min(fracao, 1.0)) * largura)
    return "▓" * cheios + "░" * (largura - cheios)


def _celula(valor: object) -> str:
    texto = "—" if valor is None or valor == "" else str(valor)
    return texto.replace("|", "\\|").replace("\n", " ")


def tabela(colunas: list[str], linhas: list[list[object]], formato: Formato = "tabela") -> str:
    """Tabela markdown, ou bullets com a 1ª coluna em negrito e o resto como `rótulo: valor`."""
    if not linhas:
        return "_Nada encontrado._"
    if formato == "lista":
        itens = []
        for linha in linhas:
            resto = " · ".join(
                f"{c}: {_celula(v)}" for c, v in zip(colunas[1:], linha[1:], strict=True)
            )
            itens.append(f"- **{_celula(linha[0])}** — {resto}" if resto else f"- {linha[0]}")
        return "\n".join(itens)
    cabecalho = "| " + " | ".join(colunas) + " |"
    separador = "|" + "|".join("---" for _ in colunas) + "|"
    corpo = ["| " + " | ".join(_celula(v) for v in linha) + " |" for linha in linhas]
    return "\n".join([cabecalho, separador, *corpo])


def paginacao(mostrados: int, total: int, offset: int) -> str:
    if total <= mostrados and offset == 0:
        return f"_{total} no total._"
    fim = offset + mostrados
    rodape = f"_Mostrando {offset + 1 if mostrados else 0}–{fim} de {total}."
    return rodape + (f" Use `offset={fim}` para ver os próximos._" if fim < total else "_")
