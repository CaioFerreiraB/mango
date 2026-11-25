"""Aviso de despesa fixa no Telegram: vence hoje 1×, atraso 1×/dia, horário, toggle, erro."""

from datetime import date, datetime, time

import pytest

from app.models.despesa_fixa import DespesaFixaOcorrencia
from app.services.despesa_fixa_alerta import verificar_e_avisar, verificar_todos
from app.services.periodo import SP
from app.telegram_client import TelegramClient, TelegramError
from tests.test_telegram import configurar, telegram_ok, vincular  # noqa: F401

D = date(2026, 3, 10)


def _em(dia: int, hora: int = 9) -> datetime:
    return datetime.combine(date(2026, 3, dia), time(hora), tzinfo=SP)


@pytest.fixture
def cenario(client_factory, db, usuario_a, monkeypatch, request):
    """Usuário com Telegram vinculado e uma despesa mensal (dia 10) criada em 01/03."""
    monkeypatch.setattr("app.routers.despesa_fixa.hoje_sp", lambda: date(2026, 3, 1))
    enviados = request.getfixturevalue("telegram_ok")
    cliente = client_factory(usuario_a)
    configurar(cliente)
    vincular(cliente, db)
    despesa = cliente.post(
        "/api/despesas-fixas",
        json={
            "descricao": "Aluguel",
            "valor_centavos": 150_000,
            "frequencia": "mensal",
            "dia_vencimento": 10,
            "inicio": "2026-03-01",
        },
    ).json()
    return cliente, despesa, enviados


def test_vence_hoje_uma_vez_e_atraso_diario(cenario, db, usuario_a):
    cliente, _, enviados = cenario
    assert verificar_e_avisar(db, usuario_a.id, _em(9)) == 0  # véspera: nada
    assert verificar_e_avisar(db, usuario_a.id, _em(10, 7)) == 0  # antes do sync_horario (8h)

    assert verificar_e_avisar(db, usuario_a.id, _em(10)) == 1
    texto = enviados[-1][0][1]
    assert "Vence hoje" in texto and "Aluguel · R$ 1.500,00" in texto
    assert enviados[-1][0][2].endswith("/despesas-fixas")  # botão abre a página
    assert verificar_e_avisar(db, usuario_a.id, _em(10, 20)) == 0  # mesmo dia: não repete

    assert verificar_e_avisar(db, usuario_a.id, _em(11)) == 1
    assert "venceu 10/03 (1 dia)" in enviados[-1][0][1]
    assert verificar_e_avisar(db, usuario_a.id, _em(11, 22)) == 0
    assert verificar_e_avisar(db, usuario_a.id, _em(12)) == 1
    assert "Atrasadas (1)" in enviados[-1][0][1] and "(2 dias)" in enviados[-1][0][1]

    # Paga → para de avisar.
    oc = db.query(DespesaFixaOcorrencia).filter_by(vencimento=D).one()
    cliente.patch(f"/api/despesas-fixas/ocorrencias/{oc.id}", json={"status": "paga"})
    db.expire_all()
    assert verificar_e_avisar(db, usuario_a.id, _em(13)) == 0
    assert len(enviados) == 3


def test_toggle_desligado_e_despesa_inativa_nao_avisam(cenario, db, usuario_a):
    cliente, despesa, enviados = cenario
    resp = cliente.patch("/api/telegram", json={"notif_despesas_fixas": False})
    assert resp.status_code == 200 and resp.json()["notif_despesas_fixas"] is False
    db.expire_all()
    assert verificar_e_avisar(db, usuario_a.id, _em(10)) == 0

    cliente.patch("/api/telegram", json={"notif_despesas_fixas": True})
    cliente.patch(f"/api/despesas-fixas/{despesa['id']}", json={"ativa": False})
    db.expire_all()
    assert verificar_e_avisar(db, usuario_a.id, _em(11)) == 0
    assert enviados == []


def test_erro_definitivo_desfaz_marca_e_incerto_mantem(cenario, db, usuario_a, monkeypatch):
    _, _, enviados = cenario

    def falha(codigo):
        def _enviar(self, *a, **kw):
            raise TelegramError(codigo)

        monkeypatch.setattr(TelegramClient, "send_message", _enviar)

    falha("indisponivel")
    assert verificar_e_avisar(db, usuario_a.id, _em(10)) == 0
    oc = db.query(DespesaFixaOcorrencia).filter_by(vencimento=D).one()
    assert oc.aviso_hoje_em is None  # não entregue com certeza → tenta de novo

    falha("envio_incerto")
    assert verificar_e_avisar(db, usuario_a.id, _em(10, 10)) == 0
    db.refresh(oc)
    assert oc.aviso_hoje_em is not None  # talvez entregue → não reenvia
    assert enviados == []


def test_job_percorre_usuarios_vinculados(cenario, db, session_factory):
    _, _, enviados = cenario
    verificar_todos(session_factory=session_factory, momento=_em(10))
    verificar_todos(session_factory=session_factory, momento=_em(10, 11))
    assert len(enviados) == 1


def test_mensagem_grande_cabe_no_limite_do_telegram():
    from app.services.despesa_fixa_alerta import _mensagem

    itens = [
        (
            DespesaFixaOcorrencia(vencimento=date(2020, 1, 1), valor_centavos=150_000_00),
            "x" * 255,
        )
        for _ in range(200)
    ]
    texto = _mensagem([], itens, D)
    assert len(texto) < 4096
    assert "Atrasadas (200)" in texto and "e mais 185" in texto
