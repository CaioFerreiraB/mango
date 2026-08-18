"""Gestão de usuários (§4.11/§5.2): aba "Usuários" em Configurações, restrita ao dono da
instância (`require_admin`). Cobre criar (com `tipo`)/listar/ativar/desativar/excluir, reenviar
convite pendente, trocar tipo, e as guardas (403 não-admin, 404 no modo local, 409
auto-desativar/auto-excluir/dados vinculados/reenviar já ativo/auto-trocar tipo).
"""

import pyotp
from sqlalchemy.orm import Session

from app.models.usuario import Usuario
from app.security.sessions import criar_sessao
from tests.helpers import criar_conta


def _convidar(client, nome="Convidado", email="convidado@mango.test", tipo="completo") -> dict:
    resp = client.post("/api/admin/usuarios", json={"nome": nome, "email": email, "tipo": tipo})
    assert resp.status_code == 201, resp.text
    return resp.json()


# --- gate: só o dono, só no self-hosted -----------------------------------------------------


def test_nao_admin_recebe_403_em_toda_rota_admin(client_factory_sh, usuario_a, usuario_b):
    a = client_factory_sh(usuario_a)
    assert a.get("/api/admin/usuarios").status_code == 403
    assert (
        a.post("/api/admin/usuarios", json={"nome": "X", "email": "x@mango.test"}).status_code
        == 403
    )
    assert a.post(f"/api/admin/usuarios/{usuario_b.id}/ativar").status_code == 403
    assert a.post(f"/api/admin/usuarios/{usuario_b.id}/desativar").status_code == 403
    assert a.post(f"/api/admin/usuarios/{usuario_b.id}/reenviar-convite").status_code == 403
    assert (
        a.post(f"/api/admin/usuarios/{usuario_b.id}/tipo", json={"tipo": "divisao"}).status_code
        == 403
    )
    assert a.delete(f"/api/admin/usuarios/{usuario_b.id}").status_code == 403


def test_admin_endpoints_404_no_modo_local(client_factory, usuario_admin):
    """`client_factory` sozinho não muda `app_mode` — fica no default (`local`)."""
    admin = client_factory(usuario_admin)
    assert admin.get("/api/admin/usuarios").status_code == 404


# --- caminho feliz ----------------------------------------------------------------------------


def test_admin_lista_cria_ativa_desativa(client_factory_sh, db: Session, usuario_admin):
    admin = client_factory_sh(usuario_admin)

    criado = _convidar(admin, tipo="divisao")
    assert criado["link_convite"].startswith("/convite/")
    usuario = db.get(Usuario, criado["usuario_id"])
    assert usuario.tipo == "divisao"
    assert usuario.ativo is True
    assert usuario.is_admin is False
    assert usuario.senha_hash is None  # placeholder pendente até aceitar o convite

    listagem = admin.get("/api/admin/usuarios").json()
    linha = next(u for u in listagem if u["id"] == criado["usuario_id"])
    assert linha["nome"] == "Convidado"
    assert linha["email"] == "convidado@mango.test"
    assert linha["tipo"] == "divisao"
    assert linha["ativo"] is True
    assert linha["is_admin"] is False
    assert linha["status"] == "so_divisao"

    desativado = admin.post(f"/api/admin/usuarios/{criado['usuario_id']}/desativar")
    assert desativado.status_code == 200
    assert desativado.json()["ativo"] is False

    reativado = admin.post(f"/api/admin/usuarios/{criado['usuario_id']}/ativar")
    assert reativado.status_code == 200
    assert reativado.json()["ativo"] is True


def test_criar_usuario_tipo_completo_por_padrao(client_factory_sh, db: Session, usuario_admin):
    admin = client_factory_sh(usuario_admin)
    resp = admin.post(
        "/api/admin/usuarios", json={"nome": "Sem tipo", "email": "semtipo@mango.test"}
    )
    assert resp.status_code == 201, resp.text
    usuario = db.get(Usuario, resp.json()["usuario_id"])
    assert usuario.tipo == "completo"


def test_convidar_email_ja_cadastrado_conflita(client_factory_sh, usuario_admin, usuario_b):
    admin = client_factory_sh(usuario_admin)
    resp = admin.post("/api/admin/usuarios", json={"nome": "Já existe", "email": usuario_b.email})
    assert resp.status_code == 409


# --- auto-gestão bloqueada + exclusão com dados vinculados -------------------------------------


def test_admin_nao_pode_desativar_ou_excluir_a_si_mesmo(client_factory_sh, usuario_admin):
    admin = client_factory_sh(usuario_admin)
    assert admin.post(f"/api/admin/usuarios/{usuario_admin.id}/desativar").status_code == 409
    assert admin.delete(f"/api/admin/usuarios/{usuario_admin.id}").status_code == 409


def test_excluir_bloqueado_quando_usuario_tem_dados_vinculados(
    client_factory_sh, db: Session, usuario_admin, usuario_a
):
    criar_conta(db, usuario_a.id, "acc-a")
    admin = client_factory_sh(usuario_admin)
    resp = admin.delete(f"/api/admin/usuarios/{usuario_a.id}")
    assert resp.status_code == 409
    assert db.get(Usuario, usuario_a.id) is not None  # continua existindo


def test_excluir_permite_convite_pendente_sem_dados(client_factory_sh, db: Session, usuario_admin):
    admin = client_factory_sh(usuario_admin)
    criado = _convidar(admin)
    resp = admin.delete(f"/api/admin/usuarios/{criado['usuario_id']}")
    assert resp.status_code == 204
    assert db.get(Usuario, criado["usuario_id"]) is None


def test_excluir_usuario_inexistente_404(client_factory_sh, usuario_admin):
    admin = client_factory_sh(usuario_admin)
    assert admin.delete("/api/admin/usuarios/999999").status_code == 404


# --- aceitar convite continua funcionando, agora criado pelo admin -----------------------------


def test_aceitar_convite_loga_e_grava_senha_e_totp(
    client_factory_sh, usuario_admin, session_factory
):
    admin = client_factory_sh(usuario_admin)
    link = _convidar(admin)["link_convite"]
    token = link.removeprefix("/convite/")

    # Passo 1: senha entra, nada é gravado ainda.
    iniciado = admin.post(f"/api/convites/{token}", json={"senha": "supersecret1"}).json()
    assert iniciado["totp_provisioning_uri"].startswith("otpauth://totp/")
    with session_factory() as verificacao:
        usuario = verificacao.query(Usuario).filter_by(email="convidado@mango.test").one()
        assert usuario.senha_hash is None

    # Passo 2: código certo → grava senha/TOTP e loga (cookies de sessão presentes).
    codigo = pyotp.TOTP(iniciado["totp_secret"]).now()
    resp = admin.post(
        "/api/convites/confirmar", json={"ticket": iniciado["ticket"], "codigo_totp": codigo}
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["email"] == "convidado@mango.test"

    with session_factory() as verificacao:
        usuario = verificacao.query(Usuario).filter_by(email="convidado@mango.test").one()
        assert usuario.senha_hash is not None
        assert usuario.totp_secret_cifrado is not None

    # Ticket já usado (convite marcado) não confirma de novo.
    resp2 = admin.post(
        "/api/convites/confirmar", json={"ticket": iniciado["ticket"], "codigo_totp": codigo}
    )
    assert resp2.status_code == 409


def test_aceitar_convite_pulando_totp(client_factory_sh, usuario_admin, session_factory):
    """2FA é opcional (§5.2, #15) — `ativar_totp: False` no passo 1 conclui sem código."""
    admin = client_factory_sh(usuario_admin)
    link = _convidar(admin, email="semtotp@mango.test")["link_convite"]
    token = link.removeprefix("/convite/")

    iniciado = admin.post(
        f"/api/convites/{token}", json={"senha": "supersecret1", "ativar_totp": False}
    ).json()
    assert iniciado["totp_secret"] is None and iniciado["totp_provisioning_uri"] is None

    resp = admin.post("/api/convites/confirmar", json={"ticket": iniciado["ticket"]})
    assert resp.status_code == 201, resp.text

    with session_factory() as verificacao:
        usuario = verificacao.query(Usuario).filter_by(email="semtotp@mango.test").one()
        assert usuario.senha_hash is not None
        assert usuario.totp_secret_cifrado is None
        assert usuario.totp_login_habilitado is False


# --- exigir_usuario_completo: conta "divisao" só acessa o módulo de divisão + o essencial ------


def _tornar_divisao(db: Session, usuario: Usuario) -> None:
    usuario.tipo = "divisao"
    db.add(usuario)
    db.commit()


def test_usuario_divisao_bloqueado_fora_do_modulo_de_divisao(
    client_factory_sh, db: Session, usuario_a
):
    _tornar_divisao(db, usuario_a)
    db.refresh(usuario_a)
    a = client_factory_sh(usuario_a)

    assert a.get("/api/transacoes").status_code == 403
    assert a.get("/api/orcamentos").status_code == 403
    assert a.get("/api/contas").status_code == 403
    assert a.get("/api/objetivos").status_code == 403

    assert a.get("/api/divisoes-despesa").status_code == 200
    assert a.get("/api/perfil").status_code == 200
    assert a.get("/api/usuarios/buscar").status_code == 200


def test_usuario_divisao_nao_vira_admin_por_engano(client_factory_sh, db: Session, usuario_a):
    """`exigir_usuario_completo` é independente de `require_admin` — tipo "divisao" sem
    `is_admin` continua barrado da gestão de usuários mesmo se tentasse acessá-la."""
    _tornar_divisao(db, usuario_a)
    db.refresh(usuario_a)
    a = client_factory_sh(usuario_a)
    assert a.get("/api/admin/usuarios").status_code == 403


# --- reenviar convite pendente ------------------------------------------------------------------


def test_reenviar_convite_invalida_anterior_e_gera_novo_link(client_factory_sh, usuario_admin):
    admin = client_factory_sh(usuario_admin)
    criado = _convidar(admin)
    usuario_id = criado["usuario_id"]
    token_antigo = criado["link_convite"].removeprefix("/convite/")

    resp = admin.post(f"/api/admin/usuarios/{usuario_id}/reenviar-convite")
    assert resp.status_code == 200, resp.text
    token_novo = resp.json()["link_convite"].removeprefix("/convite/")
    assert token_novo != token_antigo

    # Link antigo não existe mais.
    assert admin.get(f"/api/convites/{token_antigo}").status_code == 404

    # Link novo funciona normalmente.
    status_novo = admin.get(f"/api/convites/{token_novo}")
    assert status_novo.status_code == 200
    assert status_novo.json() == {"nome": "Convidado", "expirado": False, "usado": False}


def test_reenviar_convite_usuario_ja_ativo_conflita(
    client_factory_sh, usuario_admin, session_factory
):
    admin = client_factory_sh(usuario_admin)
    link = _convidar(admin)["link_convite"]
    token = link.removeprefix("/convite/")
    iniciado = admin.post(f"/api/convites/{token}", json={"senha": "supersecret1"}).json()
    codigo = pyotp.TOTP(iniciado["totp_secret"]).now()
    confirmado = admin.post(
        "/api/convites/confirmar", json={"ticket": iniciado["ticket"], "codigo_totp": codigo}
    )
    assert confirmado.status_code == 201, confirmado.text

    with session_factory() as verificacao:
        usuario_id = verificacao.query(Usuario).filter_by(email="convidado@mango.test").one().id

    resp = admin.post(f"/api/admin/usuarios/{usuario_id}/reenviar-convite")
    assert resp.status_code == 409


def test_reenviar_convite_usuario_inexistente_404(client_factory_sh, usuario_admin):
    admin = client_factory_sh(usuario_admin)
    assert admin.post("/api/admin/usuarios/999999/reenviar-convite").status_code == 404


# --- trocar tipo de acesso -----------------------------------------------------------------------


def test_admin_troca_tipo_de_usuario(client_factory_sh, usuario_admin):
    admin = client_factory_sh(usuario_admin)
    criado = _convidar(admin, tipo="completo")

    resp = admin.post(f"/api/admin/usuarios/{criado['usuario_id']}/tipo", json={"tipo": "divisao"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["tipo"] == "divisao"


def test_trocar_tipo_para_divisao_revoga_sessoes(
    client_factory_sh, db: Session, usuario_admin, usuario_a
):
    sessao = criar_sessao(db, usuario_a)
    admin = client_factory_sh(usuario_admin)

    resp = admin.post(f"/api/admin/usuarios/{usuario_a.id}/tipo", json={"tipo": "divisao"})
    assert resp.status_code == 200, resp.text

    db.refresh(sessao)
    assert sessao.revogada_em is not None


def test_trocar_tipo_para_completo_nao_revoga_sessoes(
    client_factory_sh, db: Session, usuario_admin, usuario_a
):
    _tornar_divisao(db, usuario_a)
    db.refresh(usuario_a)
    sessao = criar_sessao(db, usuario_a)
    admin = client_factory_sh(usuario_admin)

    resp = admin.post(f"/api/admin/usuarios/{usuario_a.id}/tipo", json={"tipo": "completo"})
    assert resp.status_code == 200, resp.text

    db.refresh(sessao)
    assert sessao.revogada_em is None


def test_trocar_para_o_mesmo_tipo_e_no_op(client_factory_sh, db: Session, usuario_admin, usuario_a):
    assert usuario_a.tipo == "completo"
    sessao = criar_sessao(db, usuario_a)
    admin = client_factory_sh(usuario_admin)

    resp = admin.post(f"/api/admin/usuarios/{usuario_a.id}/tipo", json={"tipo": "completo"})
    assert resp.status_code == 200, resp.text

    db.refresh(sessao)
    assert sessao.revogada_em is None


def test_admin_nao_pode_trocar_o_proprio_tipo(client_factory_sh, usuario_admin):
    admin = client_factory_sh(usuario_admin)
    resp = admin.post(f"/api/admin/usuarios/{usuario_admin.id}/tipo", json={"tipo": "divisao"})
    assert resp.status_code == 409


def test_trocar_tipo_usuario_inexistente_404(client_factory_sh, usuario_admin):
    admin = client_factory_sh(usuario_admin)
    resp = admin.post("/api/admin/usuarios/999999/tipo", json={"tipo": "divisao"})
    assert resp.status_code == 404
