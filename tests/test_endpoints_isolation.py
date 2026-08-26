"""Isolamento abrangente: para cada entidade user-owned, B nunca acessa o dado de A (§5.2)."""

import pytest

from app.models.usuario import Usuario

# (prefixo, payload de criação válido)
CASOS = [
    ("/api/objetivos", {"titulo": "Meta", "valor_alvo_centavos": 100000}),
    (
        "/api/fontes-de-renda",
        {
            "nome": "Salário",
            "tipo": "fixa",
            "valor_estimado_centavos": 1000,
            "recorrencia": "mensal",
        },
    ),
    ("/api/assinaturas", {"nome": "Streaming", "valor_centavos": 2990, "periodicidade": "mensal"}),
    ("/api/credenciais-pluggy", {"client_id": "cid", "client_secret": "sec"}),
]


@pytest.mark.parametrize("prefixo,payload", CASOS, ids=[c[0] for c in CASOS])
def test_b_nao_acessa_recurso_de_a(
    client_factory, usuario_a: Usuario, usuario_b: Usuario, prefixo: str, payload: dict
) -> None:
    client_a = client_factory(usuario_a)
    criado = client_a.post(prefixo, json=payload)
    assert criado.status_code == 201, criado.text
    recurso_id = criado.json()["id"]

    client_b = client_factory(usuario_b)
    assert client_b.get(prefixo).json() == []
    assert client_b.get(f"{prefixo}/{recurso_id}").status_code == 404
    assert client_b.patch(f"{prefixo}/{recurso_id}", json={}).status_code == 404
    assert client_b.delete(f"{prefixo}/{recurso_id}").status_code == 404

    # A continua enxergando o próprio recurso.
    assert len(client_a.get(prefixo).json()) == 1


def test_credencial_nao_devolve_segredo(client_factory, usuario_a: Usuario) -> None:
    client = client_factory(usuario_a)
    resp = client.post("/api/credenciais-pluggy", json={"client_id": "cid", "client_secret": "sec"})
    body = resp.json()
    # Nenhum campo de segredo na resposta (§5.5).
    assert "client_secret" not in body
    assert "client_secret_cifrado" not in body
    assert "client_id_cifrado" not in body
