"""Autenticação self-hosted (§5.2, #15): login 2FA, /me, logout, CSRF e recuperação de senha."""

import pyotp
from fastapi.testclient import TestClient

from app.security.sessions import CSRF_COOKIE, CSRF_HEADER
from tests.test_setup import PAYLOAD, concluir_setup


def _configurar(client: TestClient) -> str:
    """Roda o setup (2 passos) e devolve o secret TOTP. Deixa o client logado."""
    return concluir_setup(client)


def _codigo(secret: str) -> str:
    return pyotp.TOTP(secret).now()


def test_login_senha_errada(sh_client: TestClient) -> None:
    secret = _configurar(sh_client)
    sh_client.cookies.clear()
    r = sh_client.post(
        "/api/auth/login",
        json={"email": PAYLOAD["email"], "senha": "errada12", "codigo_totp": _codigo(secret)},
    )
    assert r.status_code == 401


def test_login_totp_errado(sh_client: TestClient) -> None:
    _configurar(sh_client)
    sh_client.cookies.clear()
    r = sh_client.post(
        "/api/auth/login",
        json={"email": PAYLOAD["email"], "senha": PAYLOAD["senha"], "codigo_totp": "000000"},
    )
    assert r.status_code == 401


def test_me_sem_sessao_401(sh_client: TestClient) -> None:
    _configurar(sh_client)
    sh_client.cookies.clear()
    assert sh_client.get("/api/auth/me").status_code == 401


def test_login_e_me(sh_client: TestClient) -> None:
    secret = _configurar(sh_client)
    sh_client.cookies.clear()
    r = sh_client.post(
        "/api/auth/login",
        json={"email": PAYLOAD["email"], "senha": PAYLOAD["senha"], "codigo_totp": _codigo(secret)},
    )
    assert r.status_code == 200
    me = sh_client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "dono@mango.test"


def test_csrf_bloqueia_mutacao_sem_header(sh_client: TestClient) -> None:
    _configurar(sh_client)  # já logado, com cookie csrf
    corpo = {"titulo": "Reserva", "valor_alvo_centavos": 100000}
    # Sem o header X-CSRF-Token → 403.
    assert sh_client.post("/api/objetivos", json=corpo).status_code == 403
    # Com o header ecoando o cookie csrf → passa (201).
    token = sh_client.cookies.get(CSRF_COOKIE)
    r = sh_client.post("/api/objetivos", json=corpo, headers={CSRF_HEADER: token})
    assert r.status_code == 201, r.text


def test_logout_encerra_sessao(sh_client: TestClient) -> None:
    _configurar(sh_client)
    token = sh_client.cookies.get(CSRF_COOKIE)
    assert sh_client.post("/api/auth/logout", headers={CSRF_HEADER: token}).status_code == 204
    # Cookies limpos → /me volta a 401.
    assert sh_client.get("/api/auth/me").status_code == 401


def test_recuperar_senha_via_totp(sh_client: TestClient) -> None:
    secret = _configurar(sh_client)
    sh_client.cookies.clear()
    r = sh_client.post(
        "/api/auth/recuperar-senha",
        json={
            "email": PAYLOAD["email"],
            "codigo_totp": _codigo(secret),
            "nova_senha": "novasenha9",
        },
    )
    assert r.status_code == 204
    # Senha antiga não vale mais; a nova + TOTP loga.
    antiga = sh_client.post(
        "/api/auth/login",
        json={"email": PAYLOAD["email"], "senha": PAYLOAD["senha"], "codigo_totp": _codigo(secret)},
    )
    assert antiga.status_code == 401
    nova = sh_client.post(
        "/api/auth/login",
        json={"email": PAYLOAD["email"], "senha": "novasenha9", "codigo_totp": _codigo(secret)},
    )
    assert nova.status_code == 200
