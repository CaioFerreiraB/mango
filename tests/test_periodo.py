"""Cortes de período no fuso SP (§4.10) — a função pura por trás dos filtros de data."""

from datetime import date, timedelta

from app.services.periodo import hoje_sp, janela_listagem, limites_sp


def test_janela_listagem_resolve_cada_ponta_no_fuso_sp() -> None:
    """Cada limite é independente: dar só um lado não inventa o outro."""
    ini, fim = janela_listagem(date(2026, 3, 1), date(2026, 3, 31))
    assert (ini, fim) == limites_sp(date(2026, 3, 1), date(2026, 3, 31))

    assert janela_listagem(None, None) == (None, None)
    assert janela_listagem(date(2026, 3, 1), None) == (
        limites_sp(date(2026, 3, 1), date(2026, 3, 1))[0],
        None,
    )
    assert (
        janela_listagem(None, date(2026, 3, 31))[1]
        == (limites_sp(date(2026, 3, 31), date(2026, 3, 31))[1])
    )


def test_ocultar_futuras_so_aperta_o_fim() -> None:
    """§4.2: "sem lançamentos futuros" é `fim <= hoje`. Prevalece sempre o limite mais apertado —
    o filtro nunca AFROUXA um `fim` que o usuário pediu, e nunca mexe no início."""
    hoje = hoje_sp()
    fim_de_hoje = limites_sp(hoje, hoje)[1]

    # Sem `fim` explícito, o corte de hoje assume.
    assert janela_listagem(None, None, ocultar_futuras=True) == (None, fim_de_hoje)
    # `fim` no futuro: o corte de hoje ganha.
    assert janela_listagem(None, hoje + timedelta(days=60), ocultar_futuras=True)[1] == fim_de_hoje
    # `fim` no passado: o pedido do usuário, mais apertado, ganha.
    ontem = hoje - timedelta(days=1)
    assert janela_listagem(None, ontem, ocultar_futuras=True)[1] == limites_sp(ontem, ontem)[1]
    # O início passa intacto.
    assert (
        janela_listagem(date(2026, 1, 1), None, ocultar_futuras=True)[0]
        == limites_sp(date(2026, 1, 1), date(2026, 1, 1))[0]
    )
