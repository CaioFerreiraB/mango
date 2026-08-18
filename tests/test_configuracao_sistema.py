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
