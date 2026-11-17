"""Freio de forca-bruta (§5.2, F-1): login e recuperacao de senha bloqueiam apos 5 falhas.

A ausencia desse freio deixava o TOTP de 6 digitos (login) e a recuperacao de senha (que so
depende do e-mail + codigo) bruteaveis de fora. Espelha a politica do axon: 5 falhas em 15 min
armam um bloqueio de 15 min, por chave de e-mail E de IP; o sucesso zera o contador.
"""

import pyotp
from fastapi.testclient import TestClient

from tests.test_setup import PAYLOAD, concluir_setup


def _login_errado(client: TestClient) -> int:
    return client.post(
        "/api/auth/login",
        json={"email": PAYLOAD["email"], "senha": "senha-errada-123"},
    ).status_code


def test_login_bloqueia_apos_5_falhas(sh_client: TestClient) -> None:
    concluir_setup(sh_client)
    sh_client.cookies.clear()

    assert [_login_errado(sh_client) for _ in range(5)] == [401] * 5
    # 6a tentativa: barrada antes de validar a credencial.
    assert _login_errado(sh_client) == 429
    # a senha CORRETA tambem bate no muro enquanto o bloqueio vale.
    r = sh_client.post(
        "/api/auth/login",
        json={"email": PAYLOAD["email"], "senha": PAYLOAD["senha"], "codigo_totp": "000000"},
    )
    assert r.status_code == 429


def test_login_bem_sucedido_zera_o_contador(sh_client: TestClient) -> None:
    secret = concluir_setup(sh_client)
    sh_client.cookies.clear()

    assert [_login_errado(sh_client) for _ in range(4)] == [401] * 4
    ok = sh_client.post(
        "/api/auth/login",
        json={
            "email": PAYLOAD["email"],
            "senha": PAYLOAD["senha"],
            "codigo_totp": pyotp.TOTP(secret).now(),
        },
    )
    assert ok.status_code == 200
    sh_client.cookies.clear()
    # o sucesso limpou o contador: 4 novas falhas seguem em 401, sem bloquear.
    assert [_login_errado(sh_client) for _ in range(4)] == [401] * 4


def test_recuperar_senha_bloqueia_apos_5_falhas(sh_client: TestClient) -> None:
    concluir_setup(sh_client)
    sh_client.cookies.clear()

    def _recuperar() -> int:
        return sh_client.post(
            "/api/auth/recuperar-senha",
            json={"email": PAYLOAD["email"], "codigo_totp": "000000", "nova_senha": "NovaSenha123"},
        ).status_code

    assert [_recuperar() for _ in range(5)] == [401] * 5
    assert _recuperar() == 429
