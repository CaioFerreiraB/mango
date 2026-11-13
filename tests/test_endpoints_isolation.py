"""Isolamento abrangente: para cada entidade user-owned, B nunca acessa o dado de A (§5.2)."""

import pytest
from sqlalchemy.orm import Session

from app.models.categoria import Categoria
from app.models.investimento import Investimento
from app.models.pluggy import CredencialPluggy
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


def test_credencial_troca_secret_e_mantem_client_id(
    client_factory, db: Session, usuario_a: Usuario
) -> None:
    """Girar o clientSecret em produção: PATCH só com o secret mantém o clientId."""
    client = client_factory(usuario_a)
    cred_id = client.post(
        "/api/credenciais-pluggy", json={"client_id": "cid", "client_secret": "velho"}
    ).json()["id"]

    resp = client.patch(f"/api/credenciais-pluggy/{cred_id}", json={"client_secret": "novo"})
    assert resp.status_code == 200, resp.text
    assert "client_secret" not in resp.json() and "client_secret_cifrado" not in resp.json()

    db.expire_all()
    cred = db.get(CredencialPluggy, cred_id)
    assert (cred.client_id_cifrado, cred.client_secret_cifrado) == ("cid", "novo")
    # secret vazio é recusado na fronteira (não apaga a credencial por engano)
    vazio = client.patch(f"/api/credenciais-pluggy/{cred_id}", json={"client_secret": ""})
    assert vazio.status_code == 422


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


def test_telegram_vinculo_e_preferencia_sao_individuais(client_factory, usuario_a, usuario_b, db):
    from app.models.configuracao import ConfiguracaoSistema
    from tests.test_telegram import candidato

    db.add(ConfiguracaoSistema(id=1, telegram_ativo=True, telegram_username="mango_bot"))
    db.commit()
    a, b = client_factory(usuario_a), client_factory(usuario_b)
    solicitacao = a.post("/api/telegram/vinculo").json()
    candidato(db, solicitacao)
    confirmar = {"solicitacao_id": solicitacao["solicitacao_id"]}
    assert b.post("/api/telegram/vinculo/confirmar", json=confirmar).status_code == 409
    assert b.get("/api/telegram").json()["candidato"] is None
    assert a.post("/api/telegram/vinculo/confirmar", json=confirmar).status_code == 200
    assert a.patch("/api/telegram", json={"notif_nao_revisadas": True}).status_code == 200
    assert b.delete("/api/telegram/vinculo").status_code == 204
    assert b.patch("/api/telegram", json={"notif_nao_revisadas": True}).status_code == 409
    assert b.get("/api/telegram").json()["identidade"] is None
    estado_a = a.get("/api/telegram").json()
    assert estado_a["identidade"]["usuario_id"] == "456"
    assert estado_a["notif_nao_revisadas"] is True


def test_status_do_sync_nao_vaza_entre_usuarios(
    client_factory, usuario_a: Usuario, usuario_b: Usuario
) -> None:
    from app.services import sync_manual

    resumo = {"itens": 1, "contas": 2, "transacoes": 3, "transacoes_novas": 1, "investimentos": 0}
    sync_manual._status[usuario_a.id] = {"em_andamento": False, "resumo": resumo, "erro": None}
    try:
        status_b = client_factory(usuario_b).get("/api/sync/status").json()
        assert status_b["em_andamento"] is False
        assert status_b["resumo"] is None and status_b["erro"] is None

        # A continua vendo o próprio resultado.
        assert client_factory(usuario_a).get("/api/sync/status").json()["resumo"] == resumo
    finally:
        sync_manual._status.pop(usuario_a.id, None)


def test_b_nao_acessa_conversa_nem_proposta_de_a(
    client_factory, db: Session, usuario_a: Usuario, usuario_b: Usuario
) -> None:
    """Chat web: conversa e proposta pendente de A são invisíveis (404) para B."""
    from datetime import UTC, datetime, timedelta

    from app.models.integracao import ConversaIa, MensagemIa, OperacaoIntegracao

    conversa = ConversaIa(usuario_id=usuario_a.id, titulo="privada")
    db.add(conversa)
    db.flush()
    pedido = MensagemIa(
        usuario_id=usuario_a.id, conversa_id=conversa.id, papel="user", conteudo="x"
    )
    db.add(pedido)
    db.flush()
    db.add(
        OperacaoIntegracao(
            id="op-de-a",
            usuario_id=usuario_a.id,
            mensagem_id=pedido.id,
            tipo="ia",
            status="pendente",
            payload='{"versao": "v", "chamadas": [], "confirmar": true}',
            expira_em=datetime.now(UTC) + timedelta(minutes=10),
        )
    )
    db.commit()
    rota = f"/api/ia/conversas/{conversa.id}"

    client_b = client_factory(usuario_b)
    assert client_b.get("/api/ia/conversas").json() == []
    assert client_b.get(rota).status_code == 404
    assert client_b.patch(rota, json={"titulo": "x"}).status_code == 404
    assert client_b.delete(rota).status_code == 404
    assert client_b.post("/api/ia/operacoes/op-de-a/confirmar").status_code == 404
    assert client_b.post("/api/ia/operacoes/op-de-a/cancelar").status_code == 404

    # Enviar/regenerar na conversa de A e parar uma resposta de A em andamento.
    import threading

    from app.models.integracao import PreferenciaIa
    from app.services import chat_web, integracao_auth

    c = integracao_auth.configuracao(db)
    c.ia_ativa = c.validado = True
    db.add(PreferenciaIa(usuario_id=usuario_b.id, ativa=True))
    db.commit()
    corpo = {"conversa_id": conversa.id, "texto": "oi"}
    assert client_b.post("/api/ia/mensagens", json=corpo).status_code == 404
    corpo = {"conversa_id": conversa.id, "regenerar": True}
    assert client_b.post("/api/ia/mensagens", json=corpo).status_code == 404
    db.add(PreferenciaIa(usuario_id=usuario_a.id, ativa=True))
    db.commit()
    token_a = integracao_auth.emitir(db, usuario_a.id, "web", mensagem_id=pedido.id)
    parar_a = threading.Event()
    chat_web._execucoes[usuario_a.id] = {"conversa_id": conversa.id, "parar": parar_a}
    try:
        assert client_b.post("/api/ia/execucao/parar").status_code == 204
        assert not parar_a.is_set()
        integracao_auth.resolver(db, token_a)  # credencial de A não foi revogada
    finally:
        chat_web._execucoes.clear()

    client_a = client_factory(usuario_a)
    detalhe = client_a.get(rota).json()
    assert detalhe["titulo"] == "privada" and detalhe["proposta"]["operacao_id"] == "op-de-a"
    db.refresh(db.get(OperacaoIntegracao, "op-de-a"))
    assert db.get(OperacaoIntegracao, "op-de-a").status == "pendente"
