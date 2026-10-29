"""Isolamento abrangente: para cada entidade user-owned, B nunca acessa o dado de A (§5.2)."""

import pytest
from sqlalchemy.orm import Session

from app.models.categoria import Categoria
from app.models.investimento import Investimento
from app.models.usuario import Usuario
from tests.helpers import criar_conta

# Id da taxonomia global usado pela regra de categorização (o payload de CASOS é estático).
CATEGORIA_GLOBAL = "99999999"


@pytest.fixture(autouse=True)
def _semear_categoria(db: Session) -> None:
    db.add(Categoria(pluggy_id=CATEGORIA_GLOBAL, description="Other"))
    db.commit()


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
    (
        "/api/regras-categorizacao",
        {"texto": "netflix", "tipo_match": "exato", "categoria_id": CATEGORIA_GLOBAL},
    ),
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


def test_b_nao_vincula_investimento_de_a_a_objetivo(
    client_factory, db: Session, usuario_a: Usuario, usuario_b: Usuario
) -> None:
    conta = criar_conta(db, usuario_a.id, "conta-isolamento-vinculo")
    investimento = Investimento(
        usuario_id=usuario_a.id,
        item_id=conta.item_id,
        pluggy_investment_id="investimento-isolamento-vinculo",
        type="FIXED_INCOME",
        saldo_centavos=10_000,
    )
    db.add(investimento)
    db.commit()
    client_a, client_b = client_factory(usuario_a), client_factory(usuario_b)
    objetivo_a = client_a.post(
        "/api/objetivos", json={"titulo": "Meta A", "valor_alvo_centavos": 100_000}
    ).json()["id"]
    objetivo_b = client_b.post(
        "/api/objetivos", json={"titulo": "Meta B", "valor_alvo_centavos": 100_000}
    ).json()["id"]

    for objetivo_id in (objetivo_a, objetivo_b):
        resposta = client_b.patch(
            "/api/investimentos/posicao/objetivo",
            json={"objetivo_id": objetivo_id, "investimento_ids": [investimento.id]},
        )
        assert resposta.status_code == 404, resposta.text
    db.refresh(investimento)
    assert investimento.objetivo_id is None


def test_acesso_mcp_e_por_usuario(client_factory, usuario_a: Usuario, usuario_b: Usuario) -> None:
    """`/acesso-mcp` não tem id na rota (um acesso por usuário): o isolamento é B nunca ver,
    revelar, trocar nem apagar o token de A — cada um só alcança o próprio."""
    client_a, client_b = client_factory(usuario_a), client_factory(usuario_b)
    assert client_a.patch("/api/acesso-mcp", json={"ativo": True}).status_code == 200
    token_a = client_a.get("/api/acesso-mcp/token").json()["token"]

    assert client_b.get("/api/acesso-mcp").json()["configurado"] is False
    assert client_b.get("/api/acesso-mcp/token").status_code == 404
    assert client_b.post("/api/acesso-mcp/trocar-token").status_code == 404
    assert client_b.delete("/api/acesso-mcp").status_code == 204  # apaga o (inexistente) de B

    # B ativar o próprio acesso gera outro token e não mexe no de A.
    client_b.patch("/api/acesso-mcp", json={"ativo": True})
    assert client_b.get("/api/acesso-mcp/token").json()["token"] != token_a
    assert client_a.get("/api/acesso-mcp/token").json()["token"] == token_a
    assert client_a.get("/api/acesso-mcp").json()["ativo"] is True
