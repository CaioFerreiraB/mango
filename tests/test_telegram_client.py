"""Fronteira HTTP: rejeição comprovada vs entrega incerta e redação do token."""

import logging

import httpx
import pytest

from app.telegram_client import TelegramClient, TelegramError


def cliente(handler):
    client = TelegramClient("123:nao-vazar")
    client._http.close()
    client._http = httpx.Client(
        base_url="https://api.telegram.org/bot123:nao-vazar/",
        transport=httpx.MockTransport(handler),
    )
    return client


@pytest.mark.parametrize(
    "status,corpo,codigo,repetir",
    [
        (401, {"ok": False, "error_code": 401}, "token_invalido", False),
        (403, {"ok": False, "error_code": 403}, "destinatario_bloqueou", False),
        (409, {"ok": False, "error_code": 409}, "bot_em_uso", False),
        (
            429,
            {"ok": False, "error_code": 429, "parameters": {"retry_after": 123}},
            "limite_telegram",
            True,
        ),
        (502, {"ok": False}, "envio_incerto", False),
        (200, {"ok": True, "result": None}, "envio_incerto", False),
    ],
)
def test_respostas_de_envio(status, corpo, codigo, repetir):
    with cliente(lambda req: httpx.Response(status, json=corpo)) as bot:
        with pytest.raises(TelegramError) as exc:
            bot.send_message("456", "teste")
        assert exc.value.codigo == codigo and exc.value.repetir == repetir
        assert "nao-vazar" not in str(exc.value)
        if repetir:
            assert exc.value.espera == 123


@pytest.mark.parametrize(
    "erro,repetir,codigo",
    [
        (httpx.ConnectTimeout, True, "sem_conexao"),
        (httpx.ReadTimeout, False, "envio_incerto"),
        (httpx.WriteError, False, "envio_incerto"),
    ],
)
def test_falhas_de_rede(erro, repetir, codigo):
    def falhar(req):
        raise erro(str(req.url), request=req)

    with cliente(falhar) as bot:
        with pytest.raises(TelegramError) as exc:
            bot.send_message("456", "teste")
        assert exc.value.codigo == codigo and exc.value.repetir == repetir
        assert "nao-vazar" not in str(exc.value)


def test_token_redigido_dos_logs_e_botao_opcional(caplog):
    caplog.set_level(logging.DEBUG)
    requests = []

    def responder(req):
        import json

        requests.append(json.loads(req.content))
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 42}})

    with cliente(responder) as bot:
        assert bot.send_message("456", "teste") == 42
        bot.send_message("456", "teste", "https://mango.test/transacoes?pendente=true")
    assert "nao-vazar" not in caplog.text
    assert "reply_markup" not in requests[0]
    assert requests[1]["reply_markup"]["inline_keyboard"][0][0]["url"].startswith(
        "https://mango.test/"
    )
