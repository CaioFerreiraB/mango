"""CRUD de `fonte_de_renda` via API + isolamento entre usuários (§5.2)."""

from app.models.usuario import Usuario

PAYLOAD = {
    "nome": "Salário",
    "tipo": "fixa",
    "valor_estimado_centavos": 850000,
    "recorrencia": "mensal",
    "fonte": "Empregador",
}


def test_crud_completo(client_factory, usuario_a: Usuario) -> None:
    client = client_factory(usuario_a)

    # create
    resp = client.post("/api/fontes-de-renda", json=PAYLOAD)
    assert resp.status_code == 201, resp.text
    criado = resp.json()
    assert criado["id"] > 0
    assert criado["usuario_id"] == usuario_a.id
    assert criado["valor_estimado_centavos"] == 850000
    fonte_id = criado["id"]

    # read (lista + item)
    assert client.get("/api/fontes-de-renda").json()[0]["id"] == fonte_id
    assert client.get(f"/api/fontes-de-renda/{fonte_id}").json()["nome"] == "Salário"

    # update parcial
    resp = client.patch(
        f"/api/fontes-de-renda/{fonte_id}", json={"valor_estimado_centavos": 900000}
    )
    assert resp.status_code == 200
    assert resp.json()["valor_estimado_centavos"] == 900000
    assert resp.json()["nome"] == "Salário"  # inalterado

    # delete
    assert client.delete(f"/api/fontes-de-renda/{fonte_id}").status_code == 204
    assert client.get(f"/api/fontes-de-renda/{fonte_id}").status_code == 404


def test_validacao_enum_invalido(client_factory, usuario_a: Usuario) -> None:
    client = client_factory(usuario_a)
    resp = client.post("/api/fontes-de-renda", json={**PAYLOAD, "tipo": "inexistente"})
    assert resp.status_code == 422


def test_isolamento_entre_usuarios(client_factory, usuario_a: Usuario, usuario_b: Usuario) -> None:
    client_a = client_factory(usuario_a)
    fonte_id = client_a.post("/api/fontes-de-renda", json=PAYLOAD).json()["id"]

    client_b = client_factory(usuario_b)
    # B não vê, não lê, não altera e não apaga a fonte de A.
    assert client_b.get("/api/fontes-de-renda").json() == []
    assert client_b.get(f"/api/fontes-de-renda/{fonte_id}").status_code == 404
    assert client_b.patch(f"/api/fontes-de-renda/{fonte_id}", json={"nome": "x"}).status_code == 404
    assert client_b.delete(f"/api/fontes-de-renda/{fonte_id}").status_code == 404

    # A continua enxergando a própria fonte intacta.
    assert client_a.get(f"/api/fontes-de-renda/{fonte_id}").json()["nome"] == "Salário"
