"""Formatação das respostas do MCP (app/mcp/formato.py): pt-BR, fuso SP e tabela/lista."""

from app.mcp import formato as f


def test_brl():
    assert f.brl(123456) == "R$ 1.234,56"
    assert f.brl(-1200) == "-R$ 12,00"
    assert f.brl(5) == "R$ 0,05"
    assert f.brl(None) == "—"
    assert f.reais_para_centavos(39.9) == 3990  # 39.9*100 = 3989.99… sem o round


def test_pct_e_barra():
    assert f.pct(12.345) == "12,3%"
    assert f.barra(0.5) == "▓▓▓▓▓░░░░░"
    assert f.barra(1.7) == "▓" * 10


def test_data_usa_o_dia_civil_de_sao_paulo():
    assert f.data("2026-01-01T02:00:00+00:00") == "31/12/2025"
    assert f.data("2026-03-05") == "05/03/2026"


def test_tabela_e_lista():
    assert f.tabela(["A", "B"], [["x|y", None]]).splitlines()[2] == "| x\\|y | — |"
    assert (
        f.tabela(["Nome", "Valor"], [["Ana", "R$ 1,00"]], "lista") == "- **Ana** — Valor: R$ 1,00"
    )
    assert f.tabela(["A"], []) == "_Nada encontrado._"


def test_paginacao():
    assert (
        f.paginacao(50, 312, 0) == "_Mostrando 1–50 de 312. Use `offset=50` para ver os próximos._"
    )
    assert f.paginacao(12, 62, 50) == "_Mostrando 51–62 de 62._"
    assert f.paginacao(3, 3, 0) == "_3 no total._"
