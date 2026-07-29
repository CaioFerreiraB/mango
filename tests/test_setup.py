"""First-run setup (§4.1, §4.3): fluxo em 2 passos (iniciar + confirmar TOTP) e guardas."""

import pyotp
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.models.pluggy import CredencialPluggy, ItemPluggy
from app.models.usuario import Usuario
from app.security.current_user import SESSION_COOKIE
from app.security.sessions import CSRF_COOKIE

PAYLOAD = {
    "nome": "Dono da Instância",
    "email": "Dono@Mango.test",
    "senha": "supersecret1",
    "salario_mensal": "5000.50",
    "pluggy": {"client_id": "cid-1", "client_secret": "csec-1", "item_id": "item-1"},
}


def iniciar(client: TestClient, payload=PAYLOAD) -> dict:
    r = client.post("/api/setup", json=payload)
    assert r.status_code == 200, r.text
    return r.json()


def concluir_setup(client: TestClient, payload=PAYLOAD) -> str:
    """Roda os 2 passos e devolve o secret TOTP. Deixa o client logado (cookies do confirmar)."""
    dados = iniciar(client, payload)
    r = client.post(
        "/api/setup/confirmar",
        json={
            "setup_ticket": dados["setup_ticket"],
            "codigo_totp": pyotp.TOTP(dados["totp_secret"]).now(),
        },
    )
    assert r.status_code == 201, r.text
    return dados["totp_secret"]


def test_status_nao_configurado(sh_client: TestClient) -> None:
    r = sh_client.get("/api/setup/status")
    assert r.status_code == 200
    assert r.json() == {"configured": False, "app_mode": "self_hosted"}


def test_iniciar_nao_persiste_nada(
    sh_client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    dados = iniciar(sh_client)
    assert dados["totp_provisioning_uri"].startswith("otpauth://totp/")
    assert dados["setup_ticket"] and dados["totp_secret"]
    # Passo 1 não loga nem grava.
    assert not sh_client.cookies.get(SESSION_COOKIE)
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Usuario)) == 0
    assert sh_client.get("/api/setup/status").json()["configured"] is False


def test_confirmar_codigo_errado_nao_conclui(
    sh_client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    dados = iniciar(sh_client)
    r = sh_client.post(
        "/api/setup/confirmar",
        json={"setup_ticket": dados["setup_ticket"], "codigo_totp": "000000"},
    )
    assert r.status_code == 422  # código incorreto → setup não conclui
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Usuario)) == 0
    assert sh_client.get("/api/setup/status").json()["configured"] is False


def test_confirmar_cria_dono_credencial_item(
    sh_client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    concluir_setup(sh_client)

    assert sh_client.cookies.get(SESSION_COOKIE) and sh_client.cookies.get(CSRF_COOKIE)
    with session_factory() as db:
        u = db.scalars(select(Usuario)).one()
        assert u.email == "dono@mango.test"  # normalizado
        assert u.senha_hash and u.senha_hash != "supersecret1"
        assert u.salario_mensal_centavos == 500050  # reais → centavos
        cred = db.scalars(select(CredencialPluggy)).one()
        assert cred.client_id_cifrado == "cid-1"  # EncryptedStr decifra ao ler
        item = db.scalars(select(ItemPluggy)).one()
        assert item.pluggy_item_id == "item-1" and item.credencial_id == cred.id
    assert sh_client.get("/api/setup/status").json()["configured"] is True


def test_setup_so_roda_uma_vez(sh_client: TestClient) -> None:
    concluir_setup(sh_client)
    assert sh_client.post("/api/setup", json=PAYLOAD).status_code == 409


def test_iniciar_exige_pluggy_completo(sh_client: TestClient) -> None:
    payload = {**PAYLOAD, "pluggy": {"client_id": "x", "client_secret": "y"}}  # falta item_id
    assert sh_client.post("/api/setup", json=payload).status_code == 422


def test_setup_bloqueado_no_modo_local(sh_client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "app_mode", "local")
    assert sh_client.get("/api/setup/status").json()["configured"] is True
    assert sh_client.post("/api/setup", json=PAYLOAD).status_code == 409


def test_login_apos_setup(sh_client: TestClient) -> None:
    secret = concluir_setup(sh_client)
    sh_client.cookies.clear()
    r = sh_client.post(
        "/api/auth/login",
        json={"email": PAYLOAD["email"], "senha": PAYLOAD["senha"],
              "codigo_totp": pyotp.TOTP(secret).now()},
    )
    assert r.status_code == 200, r.text
