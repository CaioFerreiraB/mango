"""Aceite Telegram: identidade verificada, segredos e fronteiras de usuário."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text

from app.models.configuracao import ConfiguracaoSistema


@pytest.fixture
def telegram_ok(monkeypatch):
    from app.telegram_client import TelegramClient

    monkeypatch.setattr(TelegramClient, "get_me", lambda self: {"id": 123, "username": "mango_bot"})
    monkeypatch.setattr(TelegramClient, "webhook_info", lambda self: {"url": ""})
    enviados = []
    monkeypatch.setattr(
        TelegramClient, "send_message", lambda self, *a, **kw: enviados.append((a, kw)) or 42
    )
    return enviados


def configurar(cliente):
    resp = cliente.patch("/api/telegram/instancia", json={"token": "123:segredo", "ativo": True})
    assert resp.status_code == 200, resp.text
    return resp.json()


def candidato(db, link, telegram_id=456, chat_type="private"):
    from app.services.telegram import processar_update

    processar_update(
        db,
        {
            "update_id": 1,
            "message": {
                "text": "/start " + link["url"].split("start=")[1],
                "chat": {"id": telegram_id, "type": chat_type},
                "from": {"id": telegram_id, "first_name": "Caio", "username": "caio"},
            },
        },
    )


def vincular(cliente, db, telegram_id=456):
    link = cliente.post("/api/telegram/vinculo").json()
    candidato(db, link, telegram_id)
    resp = cliente.post(
        "/api/telegram/vinculo/confirmar", json={"solicitacao_id": link["solicitacao_id"]}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_vinculo_privado_isolado_e_opt_in(client_factory, usuario_a, usuario_b, db, telegram_ok):
    a, b = client_factory(usuario_a), client_factory(usuario_b)
    configurar(a)
    assert a.patch("/api/telegram", json={"notif_nao_revisadas": True}).status_code == 409
    estado = vincular(a, db)
    assert estado["identidade"]["usuario_id"] == "456"
    assert estado["notif_nao_revisadas"] is False
    assert b.get("/api/telegram").json()["identidade"] is None
    assert a.patch("/api/telegram", json={"chat_id": "999"}).status_code == 422
    assert a.patch("/api/telegram", json={"notif_nao_revisadas": True}).status_code == 200
    link = b.post("/api/telegram/vinculo").json()
    candidato(db, link)
    assert (
        b.post(
            "/api/telegram/vinculo/confirmar", json={"solicitacao_id": link["solicitacao_id"]}
        ).status_code
        == 409
    )
    assert a.get("/api/telegram").json()["identidade"]["usuario_id"] == "456"
    assert a.post("/api/telegram/testar").status_code == 204
    assert a.post("/api/telegram/testar").status_code == 429
    assert len(telegram_ok) == 1
    assert a.delete("/api/telegram/vinculo").status_code == 204
    assert a.get("/api/telegram").json()["notif_nao_revisadas"] is False
    assert a.post("/api/telegram/testar").status_code == 409


def test_token_write_only_e_troca_segura(client_factory, usuario_a, db, telegram_ok, monkeypatch):
    from app.telegram_client import TelegramClient, TelegramError

    a = client_factory(usuario_a)
    configurar(a)
    vincular(a, db)
    gravado = db.execute(
        text("select telegram_token_cifrado from configuracao_sistema")
    ).scalar_one()
    assert "segredo" not in gravado
    assert "segredo" not in a.get("/api/telegram/instancia").text
    monkeypatch.setattr(TelegramClient, "get_me", lambda self: {"id": 789, "username": "outro_bot"})
    assert a.patch("/api/telegram/instancia", json={"token": "789:novo"}).status_code == 409
    assert a.get("/api/telegram").json()["vinculado"] is True
    assert (
        a.patch(
            "/api/telegram/instancia", json={"token": "789:novo", "confirmar_troca_bot": True}
        ).status_code
        == 200
    )
    assert a.get("/api/telegram").json()["vinculado"] is False

    def falhar(self):
        raise TelegramError("token_invalido")

    monkeypatch.setattr(TelegramClient, "get_me", falhar)
    assert a.patch("/api/telegram/instancia", json={"token": "789:invalido"}).status_code == 502
    db.expire_all()
    assert db.get(ConfiguracaoSistema, 1).telegram_token_cifrado == "789:novo"


def test_segredo_expirado_grupo_replay_e_solicitacao_antiga(
    client_factory, usuario_a, db, telegram_ok
):
    from app.models.telegram import ConfigTelegram

    a = client_factory(usuario_a)
    configurar(a)
    velho = a.post("/api/telegram/vinculo").json()
    novo = a.post("/api/telegram/vinculo").json()
    candidato(db, velho)
    assert a.get("/api/telegram").json()["candidato"] is None
    candidato(db, novo, chat_type="group")
    assert a.get("/api/telegram").json()["candidato"] is None
    candidato(db, novo)
    candidato(db, novo, telegram_id=999)  # segredo consumido, não troca o candidato
    assert a.get("/api/telegram").json()["candidato"]["usuario_id"] == "456"
    assert (
        a.post(
            "/api/telegram/vinculo/confirmar", json={"solicitacao_id": velho["solicitacao_id"]}
        ).status_code
        == 409
    )
    config = db.scalar(select(ConfigTelegram))
    config.vinculo_expira_em = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    assert (
        a.post(
            "/api/telegram/vinculo/confirmar", json={"solicitacao_id": novo["solicitacao_id"]}
        ).status_code
        == 409
    )


def test_permissoes_e_crud_legado(client_factory_sh, usuario_a, usuario_admin, db, telegram_ok):
    a, admin = client_factory_sh(usuario_a), client_factory_sh(usuario_admin)
    assert a.get("/api/telegram/instancia").status_code == 403
    assert (
        a.patch("/api/telegram/instancia", json={"token": "123:segredo", "ativo": True}).status_code
        == 403
    )
    assert a.delete("/api/telegram/instancia").status_code == 403
    assert a.post("/api/telegram/instancia/testar").status_code == 403
    configurar(admin)
    assert a.get("/api/telegram").status_code == 200
    assert a.patch("/api/telegram", json={"notif_nao_revisadas": False}).status_code == 200
    assert telegram_ok == []
    usuario_a.tipo = "divisao"
    db.commit()
    assert a.get("/api/telegram").status_code == 403
    assert admin.post("/api/config-telegram", json={"chat_id": "456"}).status_code in {404, 405}


def test_validacao_nao_ecoa_token_e_rejeita_webhook(
    client_factory, usuario_a, telegram_ok, monkeypatch
):
    from app.telegram_client import TelegramClient

    a = client_factory(usuario_a)
    resp = a.patch("/api/telegram/instancia", json={"token": "segredo-invalido"})
    assert resp.status_code == 422 and "segredo-invalido" not in resp.text
    monkeypatch.setattr(TelegramClient, "webhook_info", lambda self: {"url": "https://outro.test/"})
    assert (
        a.patch("/api/telegram/instancia", json={"token": "123:segredo", "ativo": True}).status_code
        == 409
    )
    assert a.get("/api/telegram").json()["configurado"] is False


def test_cursor_polling_so_avanca_apos_processar(
    client_factory, usuario_a, db, session_factory, telegram_ok, monkeypatch
):
    from app.services import telegram
    from app.telegram_client import TelegramClient

    a = client_factory(usuario_a)
    configurar(a)
    link = a.post("/api/telegram/vinculo").json()
    evento = {
        "update_id": 42,
        "message": {
            "text": "/start " + link["url"].split("start=")[1],
            "chat": {"id": 456, "type": "private"},
            "from": {"id": 456, "first_name": "Caio"},
        },
    }
    offsets = []

    def updates(self, offset):
        offsets.append(offset)
        telegram._parar.set()
        return [evento]

    monkeypatch.setattr(telegram, "SessionLocal", session_factory)
    monkeypatch.setattr(TelegramClient, "updates", updates)
    try:
        for _ in range(2):
            telegram._parar.clear()
            telegram._polling()
        assert offsets == [0, 43]
        assert a.get("/api/telegram").json()["candidato"]["usuario_id"] == "456"
    finally:
        telegram._parar.clear()


def test_confirmacoes_concorrentes_preservam_unicidade(
    client_factory, usuario_a, usuario_b, db, telegram_ok
):
    from concurrent.futures import ThreadPoolExecutor

    a, b = client_factory(usuario_a), client_factory(usuario_b)
    configurar(a)
    links = [a.post("/api/telegram/vinculo").json(), b.post("/api/telegram/vinculo").json()]
    for link in links:
        candidato(db, link)
    # A fixture devolve ORM de uma sessão compartilhada; não fazer lazy-load entre threads.
    for usuario in (usuario_a, usuario_b):
        db.refresh(usuario)
        db.expunge(usuario)

    def confirmar(par):
        cliente, link = par
        return cliente.post(
            "/api/telegram/vinculo/confirmar", json={"solicitacao_id": link["solicitacao_id"]}
        ).status_code

    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(confirmar, zip((a, b), links, strict=True))) == [200, 409]


def test_csrf_e_tokens_mcp_nao_configuram(sh_client, db):
    from app.models.acesso_mcp import AcessoMcp
    from app.models.usuario import Usuario
    from app.security.current_user import hash_token

    usuario = Usuario(nome="Agente", email="agente@teste", tipo="completo")
    db.add(usuario)
    db.flush()
    db.add(
        AcessoMcp(
            usuario_id=usuario.id,
            token_hash=hash_token("mcp-secreto"),
            token_cifrado="mcp-secreto",
            ativo=True,
            escopo="escrita",
            token_gerado_em=datetime.now(UTC),
        )
    )
    db.commit()
    assert (
        sh_client.patch("/api/telegram/instancia", json={"sync_automatico": True}).status_code
        == 403
    )
    resp = sh_client.get("/api/telegram", headers={"Authorization": "Bearer mcp-secreto"})
    assert resp.status_code == 403


def test_endereco_instalacao_capturado_sem_configuracao_manual(
    client_factory, usuario_a, db, telegram_ok
):
    cliente = client_factory(usuario_a)
    resp = cliente.patch(
        "/api/telegram/instancia",
        json={"token": "123:segredo", "ativo": True},
        headers={"Origin": "https://mango.exemplo.test:8443"},
    )
    assert resp.status_code == 200, resp.text
    db.expire_all()
    assert db.get(ConfiguracaoSistema, 1).telegram_url == "https://mango.exemplo.test:8443"
    assert "url_mango" not in resp.json()
    assert "sync_automatico" not in resp.json()
    assert (
        cliente.post(
            "/api/telegram/instancia/testar", headers={"Origin": "https://novo.mango.test"}
        ).status_code
        == 200
    )
    db.expire_all()
    assert db.get(ConfiguracaoSistema, 1).telegram_url == "https://novo.mango.test"
    for origem in (
        "null",
        "javascript:alert(1)",
        "https://pessoa:segredo@mango.test",
        "https://mango.test/caminho",
    ):
        assert (
            cliente.patch(
                "/api/telegram/instancia", json={}, headers={"Origin": origem}
            ).status_code
            == 422
        )
    assert (
        cliente.patch(
            "/api/telegram/instancia", json={}, headers={"X-Forwarded-Host": "nao-confiavel.test"}
        ).status_code
        == 200
    )
    db.expire_all()
    assert db.get(ConfiguracaoSistema, 1).telegram_url == "http://testserver"
