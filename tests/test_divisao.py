"""Divisão de contas (§4.11): rateio N-a-N, visibilidade multi-usuário, saldos e convite de
pessoa "só divisão" — endpoints e regras que a suíte genérica de isolamento não cobre (o
scaffold anterior não tinha nenhum teste)."""

from sqlalchemy.orm import Session

from app.models.usuario import Usuario


def _criar_usuario(db: Session, nome: str, email: str) -> Usuario:
    user = Usuario(nome=nome, email=email)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _despesa_igualmente(
    pago_por: int, participantes: list[int], total: int = 9000, **extra
) -> dict:
    return {
        "descricao": "Jantar",
        "valor_total_centavos": total,
        "pago_por_usuario_id": pago_por,
        "modo_divisao": "igualmente",
        "participantes": participantes,
        **extra,
    }


def _despesa_integral(pago_por: int, devedor: int, total: int = 5000) -> dict:
    return {
        "descricao": "Empréstimo",
        "valor_total_centavos": total,
        "pago_por_usuario_id": pago_por,
        "modo_divisao": "integral",
        "participantes": [devedor],
    }


# --- rateio ---------------------------------------------------------------------------------


def test_criar_despesa_igualmente_bate_com_total(client_factory, db: Session, usuario_a, usuario_b):
    usuario_c = _criar_usuario(db, "Usuário C", "c@mango.test")
    a = client_factory(usuario_a)

    # 9000 centavos / 3 pessoas = 3000 exato — sem resto pra distribuir.
    resp = a.post(
        "/api/divisoes-despesa",
        json=_despesa_igualmente(usuario_a.id, [usuario_a.id, usuario_b.id, usuario_c.id]),
    )
    assert resp.status_code == 201, resp.text
    corpo = resp.json()
    valores = {p["usuario_id"]: p["valor_centavos"] for p in corpo["participantes"]}
    assert valores == {usuario_a.id: 3000, usuario_b.id: 3000, usuario_c.id: 3000}
    assert sum(valores.values()) == 9000
    # Quem pagou (a) tem saldo positivo = soma do que os outros devem.
    assert corpo["meu_saldo_centavos"] == 6000


def test_rateio_com_resto_vai_para_ids_menores(client_factory, db: Session, usuario_a, usuario_b):
    usuario_c = _criar_usuario(db, "Usuário C", "c@mango.test")
    a = client_factory(usuario_a)

    # 100 centavos / 3 pessoas: 34 + 33 + 33, resto pro menor id primeiro.
    resp = a.post(
        "/api/divisoes-despesa",
        json=_despesa_igualmente(
            usuario_a.id, [usuario_a.id, usuario_b.id, usuario_c.id], total=100
        ),
    )
    assert resp.status_code == 201, resp.text
    por_id = sorted(resp.json()["participantes"], key=lambda p: p["usuario_id"])
    valores = [p["valor_centavos"] for p in por_id]
    assert sum(valores) == 100
    assert valores[0] == 34
    assert valores[1] == 33
    assert valores[2] == 33


def test_igualmente_inclui_pagador_mesmo_se_nao_listado(client_factory, usuario_a, usuario_b):
    """ "Todos pagam partes iguais" (§4.11) — o pagador entra na divisão mesmo sem ser listado."""
    a = client_factory(usuario_a)
    resp = a.post(
        "/api/divisoes-despesa", json=_despesa_igualmente(usuario_a.id, [usuario_b.id], total=100)
    )
    assert resp.status_code == 201, resp.text
    ids = {p["usuario_id"] for p in resp.json()["participantes"]}
    assert ids == {usuario_a.id, usuario_b.id}


def test_modo_integral_exige_exatamente_um_participante(client_factory, db, usuario_a, usuario_b):
    usuario_c = _criar_usuario(db, "Usuário C", "c@mango.test")
    a = client_factory(usuario_a)
    resp = a.post(
        "/api/divisoes-despesa",
        json={
            "descricao": "x",
            "valor_total_centavos": 1000,
            "pago_por_usuario_id": usuario_a.id,
            "modo_divisao": "integral",
            "participantes": [usuario_b.id, usuario_c.id],
        },
    )
    assert resp.status_code == 422


def test_modo_integral_devedor_nao_pode_ser_pagador(client_factory, usuario_a):
    a = client_factory(usuario_a)
    resp = a.post("/api/divisoes-despesa", json=_despesa_integral(usuario_a.id, usuario_a.id))
    assert resp.status_code == 422


def test_criar_despesa_participante_inexistente_404(client_factory, usuario_a):
    a = client_factory(usuario_a)
    resp = a.post("/api/divisoes-despesa", json=_despesa_igualmente(usuario_a.id, [999999]))
    assert resp.status_code == 404


# --- visibilidade -----------------------------------------------------------------------------


def test_terceiro_nao_ve_despesa(client_factory, db, usuario_a, usuario_b):
    usuario_c = _criar_usuario(db, "Usuário C", "c@mango.test")
    a = client_factory(usuario_a)
    c = client_factory(usuario_c)

    despesa_id = a.post(
        "/api/divisoes-despesa", json=_despesa_igualmente(usuario_a.id, [usuario_b.id])
    ).json()["id"]

    assert c.get("/api/divisoes-despesa").json() == []
    assert c.get(f"/api/divisoes-despesa/{despesa_id}").status_code == 404
    resp = c.patch(f"/api/divisoes-despesa/{despesa_id}", json={"descricao": "x"})
    assert resp.status_code == 404
    assert c.delete(f"/api/divisoes-despesa/{despesa_id}").status_code == 404


def test_participante_ve_mas_so_criador_edita_ou_exclui(client_factory, usuario_a, usuario_b):
    a = client_factory(usuario_a)
    b = client_factory(usuario_b)

    despesa_id = a.post(
        "/api/divisoes-despesa", json=_despesa_igualmente(usuario_a.id, [usuario_b.id])
    ).json()["id"]

    assert b.get(f"/api/divisoes-despesa/{despesa_id}").status_code == 200
    resp = b.patch(f"/api/divisoes-despesa/{despesa_id}", json={"descricao": "x"})
    assert resp.status_code == 404
    assert b.delete(f"/api/divisoes-despesa/{despesa_id}").status_code == 404
    # Participante consegue quitar mesmo não sendo o criador.
    assert b.post(f"/api/divisoes-despesa/{despesa_id}/quitar").status_code == 200


# --- saldos ------------------------------------------------------------------------------------


def test_resumo_e_pessoas_saldo_liquido_entre_duas_despesas(client_factory, usuario_a, usuario_b):
    a = client_factory(usuario_a)
    b = client_factory(usuario_b)

    # a paga 6000 dividido com b (igualmente) → b deve 3000 a a.
    a.post(
        "/api/divisoes-despesa",
        json=_despesa_igualmente(usuario_a.id, [usuario_a.id, usuario_b.id], total=6000),
    )
    # b paga 1000 e a deve o total (integral) → a deve 1000 a b.
    b.post("/api/divisoes-despesa", json=_despesa_integral(usuario_b.id, usuario_a.id, total=1000))

    resumo_a = a.get("/api/divisoes-despesa/resumo").json()
    assert resumo_a["saldo_a_receber_centavos"] == 2000  # 3000 - 1000, líquido
    assert resumo_a["pessoas_a_receber"] == 1
    assert resumo_a["saldo_a_pagar_centavos"] == 0
    assert resumo_a["saldo_total_centavos"] == 2000

    pessoas_a = a.get("/api/divisoes-despesa/pessoas").json()
    assert len(pessoas_a) == 1
    assert pessoas_a[0]["usuario_id"] == usuario_b.id
    assert pessoas_a[0]["saldo_centavos"] == 2000
    # Fixture `usuario_b` não passa por senha (§conftest) — aparece como "só divisão" mesmo.
    assert pessoas_a[0]["status"] == "so_divisao"


def test_quitar_remove_despesa_do_saldo_pendente(client_factory, usuario_a, usuario_b):
    a = client_factory(usuario_a)
    despesa_id = a.post(
        "/api/divisoes-despesa",
        json=_despesa_igualmente(usuario_a.id, [usuario_a.id, usuario_b.id], total=6000),
    ).json()["id"]

    assert a.get("/api/divisoes-despesa/resumo").json()["saldo_a_receber_centavos"] == 3000

    assert a.post(f"/api/divisoes-despesa/{despesa_id}/quitar").status_code == 200
    assert a.get("/api/divisoes-despesa/resumo").json()["saldo_a_receber_centavos"] == 0

    # "Pessoas" continua mostrando o contato, com saldo zerado.
    pessoas = a.get("/api/divisoes-despesa/pessoas").json()
    assert pessoas[0]["saldo_centavos"] == 0

    assert a.post(f"/api/divisoes-despesa/{despesa_id}/reabrir").status_code == 200
    assert a.get("/api/divisoes-despesa/resumo").json()["saldo_a_receber_centavos"] == 3000


def test_escopo_minhas_e_comigo(client_factory, usuario_a, usuario_b):
    a = client_factory(usuario_a)
    b = client_factory(usuario_b)

    a.post("/api/divisoes-despesa", json=_despesa_igualmente(usuario_a.id, [usuario_b.id]))
    b.post("/api/divisoes-despesa", json=_despesa_igualmente(usuario_b.id, [usuario_a.id]))

    assert len(a.get("/api/divisoes-despesa", params={"escopo": "minhas"}).json()) == 1
    assert len(a.get("/api/divisoes-despesa", params={"escopo": "comigo"}).json()) == 1
    assert len(a.get("/api/divisoes-despesa", params={"escopo": "todas"}).json()) == 2


# --- otimização de transações (§4.11-otimização) ------------------------------------------------


def test_pessoas_otimizado_colapsa_cadeia_a_b_c(
    client_factory_sh, db: Session, usuario_a, usuario_b, usuario_admin
):
    """A deve 1000 a B, B deve 1000 a C. Toggle nasce ligado — o saldo exibido deve colapsar
    pra uma única aresta direta A->C; B (líquido zero) some das duas pontas."""
    usuario_c = _criar_usuario(db, "Usuário C", "c@mango.test")
    a = client_factory_sh(usuario_a)
    b = client_factory_sh(usuario_b)
    c = client_factory_sh(usuario_c)

    a.post("/api/divisoes-despesa", json=_despesa_integral(usuario_b.id, usuario_a.id, total=1000))
    b.post("/api/divisoes-despesa", json=_despesa_integral(usuario_c.id, usuario_b.id, total=1000))

    pessoas_a = {
        p["usuario_id"]: p["saldo_centavos"] for p in a.get("/api/divisoes-despesa/pessoas").json()
    }
    assert pessoas_a.get(usuario_c.id) == -1000
    assert pessoas_a.get(usuario_b.id, 0) == 0

    pessoas_c = {
        p["usuario_id"]: p["saldo_centavos"] for p in c.get("/api/divisoes-despesa/pessoas").json()
    }
    assert pessoas_c.get(usuario_a.id) == 1000
    assert pessoas_c.get(usuario_b.id, 0) == 0

    pessoas_b = {
        p["usuario_id"]: p["saldo_centavos"] for p in b.get("/api/divisoes-despesa/pessoas").json()
    }
    assert all(saldo == 0 for saldo in pessoas_b.values())


def test_pessoas_sem_otimizacao_preserva_pareado(
    client_factory_sh, db: Session, usuario_a, usuario_b, usuario_admin
):
    usuario_c = _criar_usuario(db, "Usuário C", "c@mango.test")
    admin = client_factory_sh(usuario_admin)
    assert (
        admin.patch(
            "/api/configuracao-sistema", json={"otimizar_transacoes_divisao": False}
        ).status_code
        == 200
    )

    a = client_factory_sh(usuario_a)
    b = client_factory_sh(usuario_b)

    a.post("/api/divisoes-despesa", json=_despesa_integral(usuario_b.id, usuario_a.id, total=1000))
    b.post("/api/divisoes-despesa", json=_despesa_integral(usuario_c.id, usuario_b.id, total=1000))

    pessoas_a = {
        p["usuario_id"]: p["saldo_centavos"] for p in a.get("/api/divisoes-despesa/pessoas").json()
    }
    # Comportamento atual (100% preservado): a continua devendo a b, não a c.
    assert pessoas_a == {usuario_b.id: -1000}


def test_resumo_saldo_total_invariante_entre_bruto_e_otimizado(
    client_factory_sh, db: Session, usuario_a, usuario_b, usuario_admin
):
    """B deve 1000 a A; A deve 400 a C — saldo total de A é o mesmo nos dois modos (-1000+400=
    -600 líquido pago... na verdade A recebe 1000 de B e deve 400 a C: total = +600), mas a
    composição a_receber/a_pagar muda entre bruto e otimizado."""
    usuario_c = _criar_usuario(db, "Usuário C", "c@mango.test")
    a = client_factory_sh(usuario_a)
    admin = client_factory_sh(usuario_admin)

    a.post("/api/divisoes-despesa", json=_despesa_integral(usuario_a.id, usuario_b.id, total=1000))
    a.post("/api/divisoes-despesa", json=_despesa_integral(usuario_c.id, usuario_a.id, total=400))

    resumo_otimizado = a.get("/api/divisoes-despesa/resumo").json()

    assert (
        admin.patch(
            "/api/configuracao-sistema", json={"otimizar_transacoes_divisao": False}
        ).status_code
        == 200
    )
    resumo_bruto = a.get("/api/divisoes-despesa/resumo").json()

    assert resumo_otimizado["saldo_total_centavos"] == resumo_bruto["saldo_total_centavos"] == 600


# --- convite (usuário "só divisão") -------------------------------------------------------------
# A CRIAÇÃO do convite saiu do módulo de divisão (agora é `POST /admin/usuarios`, restrita ao
# administrador — ver tests/test_usuarios_admin.py). O que resta aqui é o efeito no módulo de
# divisão: a pessoa convidada aparece na aba "Pessoas" mesmo antes de aceitar/ter despesa em comum.


def test_pessoas_convidar_route_removida(client_factory, usuario_a):
    """A rota antiga (convite via módulo de divisão) não existe mais.

    O status exato depende do ambiente, não da aplicação: sem build da SPA em `frontend/dist`
    (o caso do CI do backend) nenhuma rota casa o caminho e vem 404; com o build, o catch-all
    `GET /{caminho:path}` do `mount_spa` casa o caminho e o POST vira 405 por método inválido.
    O que se garante aqui é que não há handler — não o número.
    """
    a = client_factory(usuario_a)
    resp = a.post(
        "/api/divisoes-despesa/pessoas/convidar",
        json={"nome": "Convidado", "email": "convidado@mango.test"},
    )
    assert resp.status_code in (404, 405)


def test_pessoa_convidada_aparece_em_pessoas_sem_despesa(client_factory_sh, usuario_admin):
    """Regressão: convidar sozinho (sem nenhuma despesa em comum ainda) não pode fazer a
    pessoa "sumir" da aba Pessoas — ela deve aparecer com saldo zerado. O convite é criado pelo
    admin (§4.11); quem vê a pessoa em "Pessoas" antes de qualquer despesa é quem convidou."""
    admin = client_factory_sh(usuario_admin)
    convidado_id = admin.post(
        "/api/admin/usuarios",
        json={"nome": "Convidado", "email": "convidado@mango.test"},
    ).json()["usuario_id"]

    pessoas = admin.get("/api/divisoes-despesa/pessoas").json()
    assert len(pessoas) == 1
    assert pessoas[0]["usuario_id"] == convidado_id
    assert pessoas[0]["saldo_centavos"] == 0
    assert pessoas[0]["status"] == "so_divisao"


def test_convite_status_pessoas_mostra_so_divisao(client_factory_sh, usuario_admin):
    admin = client_factory_sh(usuario_admin)
    convidado_id = admin.post(
        "/api/admin/usuarios",
        json={"nome": "Convidado", "email": "convidado@mango.test"},
    ).json()["usuario_id"]

    admin.post(
        "/api/divisoes-despesa",
        json=_despesa_igualmente(usuario_admin.id, [convidado_id], total=100),
    )
    pessoas = admin.get("/api/divisoes-despesa/pessoas").json()
    convidado = next(p for p in pessoas if p["usuario_id"] == convidado_id)
    assert convidado["status"] == "so_divisao"


def test_buscar_usuarios_exclui_a_si_mesmo(client_factory, usuario_a, usuario_b):
    a = client_factory(usuario_a)
    resp = a.get("/api/usuarios/buscar", params={"q": ""})
    assert resp.status_code == 200
    ids = {u["id"] for u in resp.json()}
    assert usuario_b.id in ids
    assert usuario_a.id not in ids
