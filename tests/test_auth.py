"""Autenticação self-hosted (§5.2, #15): login 2FA, /me, logout, CSRF e recuperação de senha."""

import pyotp
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.main import app as fastapi_app
from app.models.usuario import Usuario
from app.security.current_user import SESSION_COOKIE
from app.security.sessions import CSRF_COOKIE, CSRF_HEADER
from tests.test_setup import PAYLOAD, concluir_setup, concluir_setup_sem_totp


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


def test_csrf_nao_bloqueia_aceitar_convite_sem_sessao(sh_client: TestClient) -> None:
    """`/api/convites/*` roda antes de existir sessão (mesmo espírito do setup/login) — uma
    pessoa recém-convidada não tem cookie `mango_csrf` nenhum, e mesmo assim precisa conseguir
    aceitar o convite."""
    _configurar(sh_client)
    token_admin = sh_client.cookies.get(CSRF_COOKIE)
    criado = sh_client.post(
        "/api/admin/usuarios",
        json={"nome": "Convidado", "email": "convidado@mango.test", "tipo": "completo"},
        headers={CSRF_HEADER: token_admin},
    )
    assert criado.status_code == 201, criado.text
    token = criado.json()["link_convite"].removeprefix("/convite/")

    # Client totalmente novo, sem nenhum cookie — simula a pessoa convidada abrindo o link.
    anonimo = TestClient(fastapi_app)
    iniciado = anonimo.post(f"/api/convites/{token}", json={"senha": "supersecret1"})
    assert iniciado.status_code == 200, iniciado.text

    codigo = pyotp.TOTP(iniciado.json()["totp_secret"]).now()
    confirmado = anonimo.post(
        "/api/convites/confirmar",
        json={"ticket": iniciado.json()["ticket"], "codigo_totp": codigo},
    )
    assert confirmado.status_code == 201, confirmado.text


def test_logout_encerra_sessao(sh_client: TestClient) -> None:
    _configurar(sh_client)
    token = sh_client.cookies.get(CSRF_COOKIE)
    assert sh_client.post("/api/auth/logout", headers={CSRF_HEADER: token}).status_code == 204
    # Cookies limpos → /me volta a 401.
    assert sh_client.get("/api/auth/me").status_code == 401


def test_login_conta_desativada_401(
    sh_client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    secret = _configurar(sh_client)
    sh_client.cookies.clear()
    with session_factory() as db:
        usuario = db.scalars(select(Usuario)).one()
        usuario.ativo = False
        db.commit()

    r = sh_client.post(
        "/api/auth/login",
        json={"email": PAYLOAD["email"], "senha": PAYLOAD["senha"], "codigo_totp": _codigo(secret)},
    )
    assert r.status_code == 401  # mesma mensagem genérica de credencial inválida


def test_sessao_de_conta_desativada_401(
    sh_client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    _configurar(sh_client)  # já logado
    assert sh_client.get("/api/auth/me").status_code == 200

    with session_factory() as db:
        usuario = db.scalars(select(Usuario)).one()
        usuario.ativo = False
        db.commit()

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


def test_login_sem_totp_configurado_sucesso_direto(sh_client: TestClient) -> None:
    concluir_setup_sem_totp(sh_client)
    sh_client.cookies.clear()
    r = sh_client.post(
        "/api/auth/login", json={"email": PAYLOAD["email"], "senha": PAYLOAD["senha"]}
    )
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["totp_necessario"] is False
    assert corpo["usuario"]["email"] == "dono@mango.test"
    assert sh_client.cookies.get(SESSION_COOKIE)  # sessão criada de fato


def test_login_totp_configurado_mas_desabilitado_sucesso_direto(
    sh_client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    _configurar(sh_client)  # 2FA configurado por padrão no setup
    with session_factory() as db:
        usuario = db.scalars(select(Usuario)).one()
        usuario.totp_login_habilitado = False
        db.commit()
    sh_client.cookies.clear()

    r = sh_client.post(
        "/api/auth/login", json={"email": PAYLOAD["email"], "senha": PAYLOAD["senha"]}
    )
    assert r.status_code == 200, r.text
    assert r.json()["totp_necessario"] is False
    assert r.json()["usuario"]["email"] == "dono@mango.test"


def test_login_totp_habilitado_sem_codigo_retorna_totp_necessario(sh_client: TestClient) -> None:
    _configurar(sh_client)
    sh_client.cookies.clear()

    r = sh_client.post(
        "/api/auth/login", json={"email": PAYLOAD["email"], "senha": PAYLOAD["senha"]}
    )
    assert r.status_code == 200, r.text
    assert r.json() == {"totp_necessario": True, "usuario": None}
    assert not sh_client.cookies.get(SESSION_COOKIE)  # nenhuma sessão criada


def test_recuperar_senha_sem_totp_configurado_falha(sh_client: TestClient) -> None:
    concluir_setup_sem_totp(sh_client)
    sh_client.cookies.clear()
    r = sh_client.post(
        "/api/auth/recuperar-senha",
        json={"email": PAYLOAD["email"], "codigo_totp": "000000", "nova_senha": "novasenha9"},
    )
    assert r.status_code == 401  # sem 2FA configurado, não há como provar posse da conta
