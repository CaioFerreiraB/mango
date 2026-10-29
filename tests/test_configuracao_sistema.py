"""Configuração global da instância (§4.11-otimização): leitura aberta a qualquer usuário
autenticado, escrita restrita ao dono da instância (`require_admin` — mesma guarda de
`test_usuarios_admin.py`: 403 não-admin, 404 no modo local)."""


def test_leitura_devolve_true_por_padrao_sem_migration(client_factory, usuario_a):
    """Os testes sobem o schema via `create_all` (sem rodar a migration que semeia a linha) —
    prova o get-or-create do repositório."""
    a = client_factory(usuario_a)
    resp = a.get("/api/configuracao-sistema")
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"otimizar_transacoes_divisao": True}


def test_leitura_disponivel_para_usuario_comum(client_factory, usuario_a):
    a = client_factory(usuario_a)
    assert a.get("/api/configuracao-sistema").status_code == 200


def test_leitura_disponivel_para_conta_tipo_divisao(client_factory, db, usuario_a):
    from app.models.usuario import Usuario

    pessoa = Usuario(nome="Só Divisão", email="so-divisao@mango.test", tipo="divisao")
    db.add(pessoa)
    db.commit()
    db.refresh(pessoa)

    cliente = client_factory(pessoa)
    assert cliente.get("/api/configuracao-sistema").status_code == 200


def test_escrita_exige_admin_403(client_factory_sh, usuario_a):
    a = client_factory_sh(usuario_a)
    resp = a.patch("/api/configuracao-sistema", json={"otimizar_transacoes_divisao": False})
    assert resp.status_code == 403


def test_escrita_404_no_modo_local(client_factory, usuario_admin):
    """`client_factory` sozinho não muda `app_mode` — fica no default (`local`)."""
    admin = client_factory(usuario_admin)
    resp = admin.patch("/api/configuracao-sistema", json={"otimizar_transacoes_divisao": False})
    assert resp.status_code == 404


def test_admin_desliga_e_religa_o_toggle(client_factory_sh, usuario_admin):
    admin = client_factory_sh(usuario_admin)

    resp = admin.patch("/api/configuracao-sistema", json={"otimizar_transacoes_divisao": False})
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"otimizar_transacoes_divisao": False}
    assert admin.get("/api/configuracao-sistema").json() == {"otimizar_transacoes_divisao": False}

    resp = admin.patch("/api/configuracao-sistema", json={"otimizar_transacoes_divisao": True})
    assert resp.status_code == 200, resp.text
    assert admin.get("/api/configuracao-sistema").json() == {"otimizar_transacoes_divisao": True}


def test_sync_configuravel_em_conexoes_no_modo_local(client_factory, usuario_a):
    cliente = client_factory(usuario_a)
    assert cliente.get("/api/sync/configuracao").json() == {
        "sync_automatico": False,
        "sync_horario": "08:00:00",
    }
    resp = cliente.patch(
        "/api/sync/configuracao", json={"sync_automatico": True, "sync_horario": "09:15"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"sync_automatico": True, "sync_horario": "09:15:00"}
    assert cliente.get("/api/telegram").json()["sync_horario"] == "09:15:00"
    for payload in (
        {"sync_horario": "09:15:30"},
        {"sync_horario": "09:15+03:00"},
        {"sync_automatico": None},
        {"telegram_ativo": True},
    ):
        assert cliente.patch("/api/sync/configuracao", json=payload).status_code == 422
    assert (
        cliente.patch("/api/telegram/instancia", json={"sync_automatico": False}).status_code == 422
    )
    assert (
        cliente.patch(
            "/api/telegram/instancia", json={"url_mango": "https://outra.test"}
        ).status_code
        == 422
    )


def test_sync_configuracao_exige_admin_self_hosted(client_factory_sh, usuario_a, usuario_admin, db):
    comum, admin = client_factory_sh(usuario_a), client_factory_sh(usuario_admin)
    assert comum.get("/api/sync/configuracao").status_code == 200
    assert comum.patch("/api/sync/configuracao", json={"sync_automatico": True}).status_code == 403
    assert admin.patch("/api/sync/configuracao", json={"sync_automatico": True}).status_code == 200
    usuario_a.tipo = "divisao"
    db.commit()
    assert comum.get("/api/sync/configuracao").status_code == 403
