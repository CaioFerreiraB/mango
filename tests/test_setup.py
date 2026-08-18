"""First-run setup (§4.1, §4.3): fluxo em 2 passos (iniciar + confirmar TOTP) e guardas."""

import pyotp
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.models.pluggy import CredencialPluggy, Instituicao, ItemPluggy
from app.models.usuario import Usuario
from app.pluggy.client import PluggyError
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


def concluir_setup_sem_totp(client: TestClient, payload=PAYLOAD) -> None:
    """Mesmo fluxo, mas pulando o 2FA (`ativar_totp=False`) — deixa o client logado."""
    dados = iniciar(client, {**payload, "ativar_totp": False})
    assert dados["totp_secret"] is None and dados["totp_provisioning_uri"] is None
    r = client.post("/api/setup/confirmar", json={"setup_ticket": dados["setup_ticket"]})
    assert r.status_code == 201, r.text


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
        assert u.tipo == "completo"
        assert u.ativo is True
        assert u.is_admin is True  # dono da instância (§4.11) — gerencia os outros usuários
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


def test_confirmar_vincula_instituicao_escolhida(
    sh_client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    """A instituição escolhida no wizard vira o vínculo manual da conexão (§4.3)."""
    payload = {
        **PAYLOAD,
        "pluggy": {
            **PAYLOAD["pluggy"],
            "instituicao": {
                "pluggy_connector_id": 201,
                "nome": "Banco de Teste",
                "logo_url": "https://exemplo.test/logo.png",
            },
        },
    }
    concluir_setup(sh_client, payload)

    with session_factory() as db:
        inst = db.scalars(select(Instituicao)).one()
        assert (inst.nome, inst.pluggy_connector_id) == ("Banco de Teste", 201)
        assert inst.logo_url == "https://exemplo.test/logo.png"
        assert db.scalars(select(ItemPluggy)).one().instituicao_manual_id == inst.id


def test_confirmar_sem_instituicao_deixa_vinculo_vazio(
    sh_client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    """Sem escolha, o nome fica por conta do connector detectado no sync."""
    concluir_setup(sh_client)
    with session_factory() as db:
        assert db.scalars(select(ItemPluggy)).one().instituicao_manual_id is None
        assert db.scalar(select(func.count()).select_from(Instituicao)) == 0


def _pluggy_que_falha(em: str):
    """Duplo do PluggyClient que estoura em `autenticar` ou em `item`."""

    class _Falha:
        def __enter__(self):
            return self

        def __exit__(self, *exc: object) -> None:
            return None

        def autenticar(self) -> str:
            if em == "autenticar":
                raise PluggyError("POST /auth: 403")
            return "api-key"

        def item(self, item_id: str) -> dict:
            raise PluggyError("GET /items: 404")

    return lambda *a, **k: _Falha()


def test_iniciar_rejeita_credencial_invalida(
    sh_client: TestClient, session_factory: sessionmaker[Session], monkeypatch
) -> None:
    from app.services import setup as setup_service

    monkeypatch.setattr(setup_service, "PluggyClient", _pluggy_que_falha("autenticar"))
    r = sh_client.post("/api/setup", json=PAYLOAD)
    assert r.status_code == 422 and "clientId" in r.json()["detail"]
    with session_factory() as db:  # passo 1 não persiste nada, nem em caso de erro
        assert db.scalar(select(func.count()).select_from(Usuario)) == 0


def test_iniciar_rejeita_item_id_invalido(
    sh_client: TestClient, session_factory: sessionmaker[Session], monkeypatch
) -> None:
    from app.services import setup as setup_service

    monkeypatch.setattr(setup_service, "PluggyClient", _pluggy_que_falha("item"))
    r = sh_client.post("/api/setup", json=PAYLOAD)
    assert r.status_code == 422 and "itemId" in r.json()["detail"]
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Usuario)) == 0


def test_connectores_publicos_so_ate_configurar(sh_client: TestClient) -> None:
    """O catálogo do wizard é público (não há sessão ainda) e some assim que a instância nasce."""
    r = sh_client.get("/api/setup/connectores")
    assert r.status_code == 200 and len(r.json()) > 0
    assert {"pluggy_connector_id", "nome", "logo_url"} <= set(r.json()[0])

    concluir_setup(sh_client)
    assert sh_client.get("/api/setup/connectores").status_code == 409


def test_setup_bloqueado_no_modo_local(sh_client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "app_mode", "local")
    assert sh_client.get("/api/setup/status").json()["configured"] is True
    assert sh_client.post("/api/setup", json=PAYLOAD).status_code == 409


def test_login_apos_setup(sh_client: TestClient) -> None:
    secret = concluir_setup(sh_client)
    sh_client.cookies.clear()
    r = sh_client.post(
        "/api/auth/login",
        json={
            "email": PAYLOAD["email"],
            "senha": PAYLOAD["senha"],
            "codigo_totp": pyotp.TOTP(secret).now(),
        },
    )
    assert r.status_code == 200, r.text


def test_setup_pula_totp_quando_ativar_totp_false(
    sh_client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    concluir_setup_sem_totp(sh_client)
    with session_factory() as db:
        u = db.scalars(select(Usuario)).one()
        assert u.totp_secret_cifrado is None
        assert u.totp_login_habilitado is False
    # Já sai logado, mesmo sem 2FA.
    assert sh_client.get("/api/auth/me").status_code == 200
