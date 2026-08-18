"""2FA do usuário logado (§5.2, #15): cadastrar/trocar (`POST /perfil/totp/iniciar`+`/confirmar`,
step-up de senha) e habilitar/desabilitar a exigência no login (`POST /perfil/totp/habilitar`
sem step-up, `/desabilitar` com step-up)."""

import pyotp
from sqlalchemy.orm import Session

from app.models.usuario import Usuario
from app.security import passwords
from app.security.sessions import CSRF_HEADER

SENHA = "supersecret1"


def _criar_usuario_com_senha(db: Session, nome: str, email: str, **campos) -> Usuario:
    user = Usuario(nome=nome, email=email, senha_hash=passwords.hash_password(SENHA), **campos)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _codigo(secret: str) -> str:
    return pyotp.TOTP(secret).now()


# --- iniciar/confirmar: cadastrar (1ª vez) ou trocar --------------------------------------------


def test_iniciar_totp_exige_senha_atual_correta(client_factory_sh, db: Session):
    user = _criar_usuario_com_senha(db, "Sem 2FA", "semtotp@mango.test")
    client = client_factory_sh(user)
    r = client.post("/api/perfil/totp/iniciar", json={"senha_atual": "senha-errada"})
    assert r.status_code == 401


def test_cadastrar_totp_primeira_vez(client_factory_sh, db: Session):
    user = _criar_usuario_com_senha(db, "Sem 2FA", "semtotp@mango.test")
    client = client_factory_sh(user)

    iniciado = client.post("/api/perfil/totp/iniciar", json={"senha_atual": SENHA})
    assert iniciado.status_code == 200, iniciado.text
    dados = iniciado.json()
    assert dados["totp_provisioning_uri"].startswith("otpauth://totp/")

    confirmado = client.post(
        "/api/perfil/totp/confirmar",
        json={"ticket": dados["ticket"], "codigo_totp": _codigo(dados["totp_secret"])},
    )
    assert confirmado.status_code == 200, confirmado.text
    assert confirmado.json()["totp_configurado"] is True
    assert confirmado.json()["totp_login_habilitado"] is True

    db.refresh(user)
    assert user.totp_secret_cifrado == dados["totp_secret"]


def test_trocar_totp_gera_novo_secret(client_factory_sh, db: Session):
    secret_antigo = pyotp.random_base32()
    user = _criar_usuario_com_senha(
        db,
        "Com 2FA",
        "com2fa@mango.test",
        totp_secret_cifrado=secret_antigo,
        totp_login_habilitado=True,
    )
    client = client_factory_sh(user)

    iniciado = client.post("/api/perfil/totp/iniciar", json={"senha_atual": SENHA}).json()
    assert iniciado["totp_secret"] != secret_antigo

    confirmado = client.post(
        "/api/perfil/totp/confirmar",
        json={"ticket": iniciado["ticket"], "codigo_totp": _codigo(iniciado["totp_secret"])},
    )
    assert confirmado.status_code == 200, confirmado.text

    db.refresh(user)
    assert user.totp_secret_cifrado == iniciado["totp_secret"]
    assert user.totp_secret_cifrado != secret_antigo
    # Código do secret antigo não bate mais contra o secret novo persistido.
    from app.security import totp as totp_module

    assert totp_module.verificar(user.totp_secret_cifrado, _codigo(secret_antigo)) is False


def test_confirmar_totp_codigo_errado_nao_persiste(client_factory_sh, db: Session):
    user = _criar_usuario_com_senha(db, "Sem 2FA", "semtotp@mango.test")
    client = client_factory_sh(user)

    iniciado = client.post("/api/perfil/totp/iniciar", json={"senha_atual": SENHA}).json()
    resp = client.post(
        "/api/perfil/totp/confirmar", json={"ticket": iniciado["ticket"], "codigo_totp": "000000"}
    )
    assert resp.status_code == 422

    db.refresh(user)
    assert user.totp_secret_cifrado is None
    assert user.totp_login_habilitado is False


def test_confirmar_totp_ticket_de_outro_usuario(client_factory_sh, db: Session):
    user_a = _criar_usuario_com_senha(db, "A", "a-totp@mango.test")
    user_b = _criar_usuario_com_senha(db, "B", "b-totp@mango.test")
    client_a = client_factory_sh(user_a)
    client_b = client_factory_sh(user_b)

    iniciado = client_a.post("/api/perfil/totp/iniciar", json={"senha_atual": SENHA}).json()
    resp = client_b.post(
        "/api/perfil/totp/confirmar",
        json={"ticket": iniciado["ticket"], "codigo_totp": _codigo(iniciado["totp_secret"])},
    )
    assert resp.status_code == 422  # ticket não pertence à sessão de B

    db.refresh(user_b)
    assert user_b.totp_secret_cifrado is None


# --- habilitar/desabilitar a exigência no login --------------------------------------------------


def test_habilitar_totp_login_sem_senha(client_factory_sh, db: Session):
    user = _criar_usuario_com_senha(
        db,
        "Com 2FA",
        "com2fa@mango.test",
        totp_secret_cifrado=pyotp.random_base32(),
        totp_login_habilitado=False,
    )
    client = client_factory_sh(user)
    # Sem `senha_atual` no corpo — não é exigida para habilitar.
    resp = client.post("/api/perfil/totp/habilitar")
    assert resp.status_code == 204

    db.refresh(user)
    assert user.totp_login_habilitado is True


def test_habilitar_totp_login_sem_totp_configurado_falha(client_factory_sh, db: Session):
    user = _criar_usuario_com_senha(db, "Sem 2FA", "semtotp@mango.test")
    client = client_factory_sh(user)
    assert client.post("/api/perfil/totp/habilitar").status_code == 422


def test_desabilitar_totp_login_exige_senha_atual(client_factory_sh, db: Session):
    user = _criar_usuario_com_senha(
        db,
        "Com 2FA",
        "com2fa@mango.test",
        totp_secret_cifrado=pyotp.random_base32(),
        totp_login_habilitado=True,
    )
    client = client_factory_sh(user)

    errada = client.post("/api/perfil/totp/desabilitar", json={"senha_atual": "senha-errada"})
    assert errada.status_code == 401
    db.refresh(user)
    assert user.totp_login_habilitado is True  # nada mudou

    certa = client.post("/api/perfil/totp/desabilitar", json={"senha_atual": SENHA})
    assert certa.status_code == 204
    db.refresh(user)
    assert user.totp_login_habilitado is False
    assert user.totp_secret_cifrado is not None  # 2FA continua configurado (só a exigência caiu)


# --- guardas: modo local e CSRF ------------------------------------------------------------------


def test_endpoints_totp_404_no_modo_local(client_factory, usuario_a):
    """`client_factory` sozinho fica no modo `local` (default) — sem `senha_hash` pra step-up."""
    client = client_factory(usuario_a)
    assert client.post("/api/perfil/totp/habilitar").status_code == 404


def test_endpoints_totp_exigem_csrf(client_factory_sh, db: Session):
    user = _criar_usuario_com_senha(
        db,
        "Com 2FA",
        "com2fa@mango.test",
        totp_secret_cifrado=pyotp.random_base32(),
        totp_login_habilitado=False,
    )
    client = client_factory_sh(user)
    del client.headers[CSRF_HEADER]  # remove o header que `client_factory_sh` já ecoa por padrão
    assert client.post("/api/perfil/totp/habilitar").status_code == 403
