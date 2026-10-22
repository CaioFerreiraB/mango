"""MCP (docs/mcp.md): token de acesso, alcance do Bearer e as tools ponta a ponta via /mcp.

As tools chamam a API em processo repassando o token, então estes testes rodam a autenticação
real (sem sobrescrever `get_current_user`) — só o `get_db` aponta para a DB de teste.
"""

import json
from collections.abc import Callable, Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db.session import get_db
from app.main import app as fastapi_app
from app.mcp import ciclo_mcp
from app.models.acesso_mcp import AcessoMcp
from app.models.assinatura import Assinatura
from app.models.cartao_fatura import Cartao, Fatura
from app.models.categoria import Categoria
from app.models.objetivo import Objetivo
from app.models.transacao import Transacao
from app.models.usuario import Usuario
from app.security.current_user import hash_token
from tests.helpers import criar_conta, criar_conta_no_item, criar_prereqs_conta


@pytest.fixture
def cliente(
    session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    from app.config import settings

    monkeypatch.setattr(settings, "app_mode", "self_hosted")

    def _get_db() -> Iterator[Session]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    fastapi_app.dependency_overrides[get_db] = _get_db
    # Só o ciclo do MCP no lifespan: o real faz bootstrap (migrations, guarda de chaves de
    # produção, ingestão CVM em rede) — fora do escopo destes testes.
    monkeypatch.setattr(fastapi_app.router, "lifespan_context", lambda _app: ciclo_mcp())
    with TestClient(fastapi_app) as client:
        yield client
    fastapi_app.dependency_overrides.clear()


def ativar_mcp(
    db: Session, user: Usuario, escopo: str = "escrita", token: str | None = None
) -> str:
    token = token or f"mango_teste_{user.id}_{escopo}"
    db.add(
        AcessoMcp(
            usuario_id=user.id,
            ativo=True,
            escopo=escopo,
            token_hash=hash_token(token),
            token_cifrado=token,
            token_gerado_em=datetime.now(UTC),
        )
    )
    db.commit()
    return token


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


ChamarTool = Callable[..., dict]


@pytest.fixture
def chamar(cliente: TestClient) -> ChamarTool:
    """`chamar(token, tool, **args)` → o `result` JSON-RPC do tools/call (stateless, sem sessão)."""

    def _chamar(token: str, tool: str, **args) -> dict:
        resp = cliente.post(
            "/mcp",
            headers={**bearer(token), "Accept": "application/json, text/event-stream"},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": tool, "arguments": args},
            },
        )
        assert resp.status_code == 200, resp.text
        corpo = resp.json()
        assert "result" in corpo, corpo
        return corpo["result"]

    return _chamar


def texto(resultado: dict) -> str:
    return resultado["content"][0]["text"]


# --- autenticação por token -----------------------------------------------------------------


def test_bearer_valido_acessa_rota_permitida(cliente, db, usuario_a):
    criar_conta(db, usuario_a.id, "acc-1", nome="Corrente A")
    token = ativar_mcp(db, usuario_a)
    resp = cliente.get("/api/contas", headers=bearer(token))
    assert resp.status_code == 200
    assert [c["nome"] for c in resp.json()] == ["Corrente A"]


def test_bearer_fora_da_allowlist_da_403(cliente, db, usuario_a):
    token = ativar_mcp(db, usuario_a)
    for metodo, caminho in [
        ("GET", "/api/perfil"),
        ("GET", "/api/acesso-mcp"),
        ("GET", "/api/acesso-mcp/token"),
        ("POST", "/api/acesso-mcp/trocar-token"),
        ("GET", "/api/credenciais-pluggy"),
        ("POST", "/api/sync"),
        ("PATCH", "/api/configuracao-sistema"),
        ("GET", "/api/orcamentos-mensais"),
        ("POST", "/api/categorias"),
    ]:
        resp = cliente.request(metodo, caminho, headers=bearer(token), json={})
        assert resp.status_code == 403, (metodo, caminho, resp.status_code)


def test_token_de_leitura_nao_escreve(cliente, db, usuario_a):
    token = ativar_mcp(db, usuario_a, escopo="leitura")
    assert cliente.get("/api/objetivos", headers=bearer(token)).status_code == 200
    resp = cliente.post(
        "/api/objetivos", headers=bearer(token), json={"titulo": "X", "valor_alvo_centavos": 1}
    )
    assert resp.status_code == 403
    assert "leitura" in resp.json()["detail"]


def test_token_invalido_ou_desativado_da_401(cliente, db, usuario_a):
    token = ativar_mcp(db, usuario_a)
    assert cliente.get("/api/contas", headers=bearer("mango_nao_existe")).status_code == 401
    acesso = db.query(AcessoMcp).filter_by(usuario_id=usuario_a.id).one()
    acesso.ativo = False
    db.commit()
    assert cliente.get("/api/contas", headers=bearer(token)).status_code == 401
    acesso.ativo = True
    db.commit()
    assert cliente.get("/api/contas", headers=bearer(token)).status_code == 200  # mesmo token


def test_usuario_desativado_perde_o_token(cliente, db, usuario_a):
    token = ativar_mcp(db, usuario_a)
    usuario_a.ativo = False
    db.commit()
    assert cliente.get("/api/contas", headers=bearer(token)).status_code == 401


def test_bearer_ignora_cookie_de_sessao_e_dispensa_csrf(cliente, db, usuario_a, usuario_b):
    from app.security.sessions import criar_sessao

    sessao_b = criar_sessao(db, usuario_b)
    token_a = ativar_mcp(db, usuario_a)
    cliente.cookies.set("mango_session", sessao_b.id)
    # Mutação sem cookie/header de CSRF passa: com Bearer não há credencial ambiente.
    resp = cliente.post(
        "/api/objetivos",
        headers=bearer(token_a),
        json={"titulo": "Viagem", "valor_alvo_centavos": 100},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["usuario_id"] == usuario_a.id
    # Bearer inválido NÃO cai para o cookie.
    assert cliente.get("/api/contas", headers=bearer("mango_x")).status_code == 401


def test_mcp_sem_token_da_401(cliente):
    resp = cliente.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert resp.status_code == 401
    assert resp.headers["www-authenticate"] == "Bearer"


def test_isolamento_entre_usuarios(chamar, db, usuario_a, usuario_b):
    criar_conta(db, usuario_a.id, "acc-a", nome="Conta da A")
    token_b = ativar_mcp(db, usuario_b)
    resultado = chamar(token_b, "listar_contas")
    assert "Conta da A" not in json.dumps(resultado)


# --- tools ----------------------------------------------------------------------------------


def test_listar_contas(chamar, db, usuario_a):
    criar_conta(db, usuario_a.id, "acc-1", nome="Corrente A", saldo_centavos=123456)
    token = ativar_mcp(db, usuario_a, escopo="leitura")
    resultado = chamar(token, "listar_contas")
    assert not resultado.get("isError")
    assert "| Corrente A | Conta corrente | R$ 1.234,56 |" in texto(resultado)
    assert resultado["structuredContent"]["saldo_total_bancos_centavos"] == 123456
    lista = chamar(token, "listar_contas", formato="lista")
    assert "- **" in texto(lista)


# --- cenário com dados ----------------------------------------------------------------------


def _tx(db: Session, usuario: Usuario, conta_id: int, pid: str, valor: int, **campos) -> Transacao:
    obj = Transacao(
        usuario_id=usuario.id,
        conta_id=conta_id,
        pluggy_transaction_id=pid,
        date=campos.pop("date", datetime(2026, 3, 10, 15, tzinfo=UTC)),
        amount_centavos=valor,
        currency_code="BRL",
        type="DEBIT" if valor < 0 else "CREDIT",
        status="POSTED",
        **campos,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@pytest.fixture
def cenario(db: Session, usuario_a: Usuario) -> dict:
    db.add_all(
        [
            Categoria(
                pluggy_id="02000000", description="Food", description_translated="Alimentação"
            ),
            Categoria(
                pluggy_id="03000000", description="Transport", description_translated="Transporte"
            ),
            Categoria(pluggy_id="01000000", description="Income", description_translated="Renda"),
        ]
    )
    db.commit()
    inst, item = criar_prereqs_conta(db, usuario_a.id)
    corrente = criar_conta_no_item(
        db, usuario_a.id, item, inst, "acc-c", nome="Corrente", saldo_centavos=500000
    )
    cartao = criar_conta_no_item(
        db,
        usuario_a.id,
        item,
        inst,
        "acc-k",
        nome="Cartão Roxo",
        type="CREDIT",
        subtype="CREDIT_CARD",
        saldo_centavos=25000,
    )
    db.add(
        Cartao(
            conta_id=cartao.id,
            brand="MASTERCARD",
            credit_limit_centavos=100000,
            available_credit_limit_centavos=75000,
        )
    )
    fatura = Fatura(
        usuario_id=usuario_a.id,
        cartao_id=cartao.id,
        pluggy_bill_id="b1",
        due_date=datetime(2026, 3, 20, tzinfo=UTC),
        total_amount_centavos=25000,
    )
    db.add(fatura)
    objetivo = Objetivo(
        usuario_id=usuario_a.id, titulo="Viagem ao Japão", valor_alvo_centavos=1000000
    )
    db.add(objetivo)
    db.commit()
    mercado = _tx(
        db,
        usuario_a,
        corrente.id,
        "t-mercado",
        -15000,
        description="SUPERMERCADO BOM",
        categoria_pluggy_id="02000000",
    )
    uber = _tx(
        db,
        usuario_a,
        corrente.id,
        "t-uber",
        -3000,
        description="UBER *TRIP",
        categoria_pluggy_id="03000000",
    )
    salario = _tx(
        db,
        usuario_a,
        corrente.id,
        "t-sal",
        800000,
        description="SALARIO",
        categoria_pluggy_id="01000000",
    )
    # Compra de cartão: DEBIT com valor POSITIVO (como o Pluggy manda).
    compra = Transacao(
        usuario_id=usuario_a.id,
        conta_id=cartao.id,
        pluggy_transaction_id="t-cartao",
        date=datetime(2026, 3, 5, tzinfo=UTC),
        amount_centavos=25000,
        currency_code="BRL",
        type="DEBIT",
        status="POSTED",
        description="RESTAURANTE",
        categoria_pluggy_id="02000000",
        bill_id=fatura.id,
    )
    db.add(compra)
    db.commit()
    return {
        "corrente": corrente,
        "cartao": cartao,
        "fatura": fatura,
        "objetivo": objetivo,
        "mercado": mercado,
        "uber": uber,
        "salario": salario,
        "compra": compra,
    }


def test_listar_transacoes_com_filtros_por_nome(chamar, db, usuario_a, cenario):
    token = ativar_mcp(db, usuario_a, escopo="leitura")
    r = chamar(token, "listar_transacoes", categoria="alimentacao")  # sem acento/caixa
    ids = {t["id"] for t in r["structuredContent"]["transacoes"]}
    assert ids == {cenario["mercado"].id, cenario["compra"].id}
    assert "| SUPERMERCADO BOM | Corrente | Alimentação | -R$ 150,00 | a revisar |" in texto(r)
    # Compra de cartão (DEBIT positivo) sai como despesa.
    assert "| RESTAURANTE | Cartão Roxo | Alimentação | -R$ 250,00 |" in texto(r)

    r = chamar(token, "listar_transacoes", tipo="receita", conta="Corrente")
    assert [t["id"] for t in r["structuredContent"]["transacoes"]] == [cenario["salario"].id]

    r = chamar(token, "listar_transacoes", limite=2)
    assert "Use `offset=2`" in texto(r)


def test_nome_inexistente_ou_ambiguo_vira_erro(chamar, db, usuario_a, cenario):
    token = ativar_mcp(db, usuario_a, escopo="leitura")
    r = chamar(token, "listar_transacoes", categoria="Educação")
    assert r["isError"] and "não encontrad" in texto(r)
    r = chamar(token, "listar_transacoes", conta="r")  # Corrente e Cartão Roxo contêm "r"
    assert r["isError"] and "ambíguo" in texto(r)


def test_buscar_e_obter_transacao(chamar, db, usuario_a, cenario):
    token = ativar_mcp(db, usuario_a, escopo="leitura")
    r = chamar(token, "buscar_transacoes", termo="uber", inicio="2026-01-01")
    assert [t["id"] for t in r["structuredContent"]["transacoes"]] == [cenario["uber"].id]
    r = chamar(token, "obter_transacao", transacao_id=cenario["uber"].id)
    assert "Transporte (sugestão do banco)" in texto(r)


def test_atualizar_transacoes_em_lote_com_falha_parcial(chamar, db, usuario_a, cenario):
    token = ativar_mcp(db, usuario_a)
    ids = [cenario["mercado"].id, cenario["uber"].id, 999999]
    r = chamar(token, "atualizar_transacoes", ids=ids, categoria="Alimentação", revisada=True)
    assert not r.get("isError")
    assert "2 de 3" in texto(r)
    assert [x["id"] for x in r["structuredContent"]["falhas"]] == [999999]
    db.expire_all()
    uber = db.get(Transacao, cenario["uber"].id)
    assert (uber.categoria_override_id, uber.categoria_ajustada_usuario, uber.revisada) == (
        "02000000",
        True,
        True,
    )

    r = chamar(token, "atualizar_transacoes", ids=[cenario["uber"].id], restaurar_categoria=True)
    db.expire_all()
    assert db.get(Transacao, cenario["uber"].id).categoria_override_id is None


def test_regra_do_router_vale_no_mcp(chamar, db, usuario_a, cenario):
    """Categoria de cobrança de assinatura vem da assinatura — o MCP herda a recusa do router."""
    assinatura = Assinatura(
        usuario_id=usuario_a.id, nome="Uber One", valor_centavos=3000, periodicidade="mensal"
    )
    db.add(assinatura)
    db.commit()
    token = ativar_mcp(db, usuario_a)
    uid = cenario["uber"].id
    chamar(token, "atualizar_transacoes", ids=[uid], assinatura_id=assinatura.id)
    r = chamar(token, "atualizar_transacoes", ids=[uid], categoria="Alimentação")
    assert "vem da assinatura" in r["structuredContent"]["falhas"][0]["erro"]


def test_token_de_leitura_nao_altera_pelo_mcp(chamar, db, usuario_a, cenario):
    token = ativar_mcp(db, usuario_a, escopo="leitura")
    r = chamar(token, "atualizar_transacoes", ids=[cenario["uber"].id], revisada=True)
    assert "leitura" in r["structuredContent"]["falhas"][0]["erro"]
    db.expire_all()
    assert db.get(Transacao, cenario["uber"].id).revisada is False


def test_cartoes_e_faturas(chamar, db, usuario_a, cenario):
    token = ativar_mcp(db, usuario_a, escopo="leitura")
    r = chamar(token, "listar_cartoes")
    assert "| Cartão Roxo | MASTERCARD | R$ 250,00 | R$ 1.000,00 | R$ 750,00 | 25% |" in texto(r)
    r = chamar(token, "listar_faturas", cartao="Cartão Roxo")
    assert [x["id"] for x in r["structuredContent"]["itens"]] == [cenario["fatura"].id]
    r = chamar(token, "obter_fatura", fatura_id=cenario["fatura"].id)
    assert "| Alimentação | R$ 250,00 | 100,0% |" in texto(r)
    assert len(r["structuredContent"]["transacoes"]) == 1


def test_objetivos_e_vinculo(chamar, db, usuario_a, cenario):
    token = ativar_mcp(db, usuario_a)
    r = chamar(
        token, "vincular_objetivo", tipo="conta", item_id=cenario["corrente"].id, objetivo="japão"
    )
    assert not r.get("isError"), texto(r)
    r = chamar(token, "obter_objetivo", objetivo=cenario["objetivo"].id)
    assert "| conta |" in texto(r) and "R$ 5.000,00" in texto(r)
    r = chamar(token, "listar_objetivos")
    assert "50%" in texto(r)
    r = chamar(
        token, "vincular_objetivo", tipo="conta", item_id=cenario["corrente"].id, objetivo=None
    )
    assert "desvinculad" in texto(r)


def test_ciclo_de_assinatura(chamar, db, usuario_a, cenario):
    token = ativar_mcp(db, usuario_a)
    r = chamar(
        token,
        "criar_assinatura",
        nome="Netflix",
        valor=39.9,
        periodicidade="mensal",
        categoria="Alimentação",
    )
    assert r["structuredContent"]["valor_centavos"] == 3990
    aid = r["structuredContent"]["id"]
    r = chamar(token, "listar_assinaturas")
    assert "R$ 39,90" in texto(r) and "Total mensal equivalente" in texto(r)
    r = chamar(token, "atualizar_assinatura", assinatura_id=aid, ativa=False)
    assert r["structuredContent"]["ativa"] is False
    assert "Netflix" not in texto(chamar(token, "listar_assinaturas"))
    r = chamar(token, "excluir_assinatura", assinatura_id=aid)
    assert "excluída" in texto(r)
    assert db.get(Assinatura, aid) is None

    r = chamar(token, "rejeitar_candidato_assinatura", transacao_ids=[cenario["uber"].id])
    db.expire_all()
    assert db.get(Transacao, cenario["uber"].id).nao_e_assinatura is True


def test_divisao_criar_saldo_quitar(chamar, db, usuario_a, usuario_b):
    token = ativar_mcp(db, usuario_a)
    r = chamar(token, "criar_divisao", descricao="Pizza", valor=100, participantes=["usuário b"])
    assert not r.get("isError"), texto(r)
    did = r["structuredContent"]["id"]
    assert {p["valor_centavos"] for p in r["structuredContent"]["participantes"]} == {5000}

    r = chamar(token, "saldos_divisao", pessoa="Usuário B")
    assert "**Usuário B** te deve R$ 50,00" in texto(r)
    assert [d["id"] for d in r["structuredContent"]["divisoes_abertas"]] == [did]
    r = chamar(token, "saldos_divisao")
    assert "A receber: **R$ 50,00**" in texto(r)

    chamar(token, "quitar_divisao", divisao_id=did)
    assert "quites" in texto(chamar(token, "saldos_divisao", pessoa=usuario_b.id))
    chamar(token, "reabrir_divisao", divisao_id=did)
    assert "Pizza" in texto(chamar(token, "listar_divisoes", apenas_abertas=True))
    assert "excluída" in texto(chamar(token, "excluir_divisao", divisao_id=did))


def test_divisao_pessoa_ambigua_e_conta_so_divisao(chamar, db, usuario_a):
    from tests.conftest import _criar_usuario

    _criar_usuario(db, "Ana Souza", "ana1@mango.test")
    _criar_usuario(db, "Ana Lima", "ana2@mango.test")
    token = ativar_mcp(db, usuario_a)
    r = chamar(token, "criar_divisao", descricao="Bar", valor=90, participantes=["Ana"])
    assert r["isError"] and "ambíguo" in texto(r)
    assert "ana1@" not in texto(r)  # busca de pessoas nunca expõe e-mail

    so_divisao = _criar_usuario(db, "Bia", "bia@mango.test", tipo="divisao")
    token_bia = ativar_mcp(db, so_divisao)
    assert chamar(token_bia, "listar_contas")["isError"]
    assert not chamar(token_bia, "saldos_divisao").get("isError")


def test_tools_de_leitura_sem_dados_nao_quebram(chamar, db, usuario_a, cenario):
    token = ativar_mcp(db, usuario_a, escopo="leitura")
    for tool, args in [
        ("listar_categorias", {}),
        ("listar_categorias", {"busca": "trans", "formato": "lista"}),
        ("obter_conta", {"conta": "Cartão Roxo"}),
        ("listar_orcamentos", {}),
        ("listar_candidatos_assinatura", {}),
        ("listar_pessoas_divisao", {}),
        ("resumo_financeiro", {"inicio": "2026-03-01", "fim": "2026-03-31"}),
        ("resumo_investimentos", {}),
        ("listar_investimentos", {}),
        ("listar_fontes_de_renda", {}),
    ]:
        r = chamar(token, tool, **args)
        assert not r.get("isError"), (tool, texto(r))
    r = chamar(token, "resumo_financeiro", inicio="2026-03-01", fim="2026-03-31")
    assert "**Entradas:** R$ 8.000,00" in texto(r)


def test_catalogo_anota_leitura_e_destrutivas(cliente, db, usuario_a):
    token = ativar_mcp(db, usuario_a)
    resp = cliente.post(
        "/mcp",
        headers={**bearer(token), "Accept": "application/json, text/event-stream"},
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )
    tools = {t["name"]: t for t in resp.json()["result"]["tools"]}
    destrutivas = {n for n, t in tools.items() if t["annotations"].get("destructiveHint")}
    assert destrutivas == {"excluir_assinatura", "excluir_divisao"}
    assert tools["listar_transacoes"]["annotations"]["readOnlyHint"] is True
    assert all(t.get("description") for t in tools.values())


def _rpc(cliente: TestClient, token: str, metodo: str, params: dict | None = None) -> dict:
    resp = cliente.post(
        "/mcp",
        headers={**bearer(token), "Accept": "application/json, text/event-stream"},
        json={"jsonrpc": "2.0", "id": 1, "method": metodo, "params": params or {}},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["result"]


def test_grafico_devolve_png_tabela_e_spec(chamar, db, usuario_a, cenario):
    import base64

    token = ativar_mcp(db, usuario_a, escopo="leitura")
    for tipo, args in [
        ("gastos_por_categoria", {"inicio": "2026-03-01", "fim": "2026-03-31"}),
        ("receitas_vs_despesas", {"inicio": "2026-01-01", "fim": "2026-03-31"}),
        ("saldo_contas", {}),
        ("orcamento_mes", {"ano": 2026, "mes": 3}),
        ("faturas_cartao", {"cartao": "Cartão Roxo"}),
    ]:
        r = chamar(token, "grafico", tipo=tipo, **args)
        assert not r.get("isError"), (tipo, texto(r))
        imagem = next(c for c in r["content"] if c["type"] == "image")
        assert imagem["mimeType"] == "image/png"
        assert base64.b64decode(imagem["data"]).startswith(b"\x89PNG"), tipo
        assert r["structuredContent"]["spec"]["$schema"].startswith("https://vega.github.io")
    r = chamar(token, "grafico", tipo="gastos_por_categoria", inicio="2026-03-01", fim="2026-03-31")
    assert "| Alimentação | R$ 400,00 |" in texto(r)  # cartão (DEBIT positivo) soma, não abate
    assert chamar(token, "grafico", tipo="faturas_cartao")["isError"]  # sem cartão


def test_app_do_grafico_e_anunciado(cliente, db, usuario_a):
    token = ativar_mcp(db, usuario_a, escopo="leitura")
    tools = {t["name"]: t for t in _rpc(cliente, token, "tools/list")["tools"]}
    assert tools["grafico"]["_meta"]["ui"]["resourceUri"] == "ui://mango/grafico"
    recursos = _rpc(cliente, token, "resources/list")["resources"]
    assert [r["mimeType"] for r in recursos if r["uri"] == "ui://mango/grafico"] == [
        "text/html;profile=mcp-app"
    ]
    lido = _rpc(cliente, token, "resources/read", {"uri": "ui://mango/grafico"})["contents"][0]
    assert "vegaEmbed" in lido["text"]


def test_prompts_listados(cliente, db, usuario_a):
    token = ativar_mcp(db, usuario_a, escopo="leitura")
    nomes = {p["name"] for p in _rpc(cliente, token, "prompts/list")["prompts"]}
    assert nomes == {"revisar_pendentes", "resumo_do_mes", "acerto_de_contas"}
    r = _rpc(
        cliente, token, "prompts/get", {"name": "acerto_de_contas", "arguments": {"pessoa": "Ana"}}
    )
    assert "pessoa='Ana'" in r["messages"][0]["content"]["text"]


def test_modo_local_sem_token_so_aceita_localhost(cliente, db, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "app_mode", "local")
    corpo = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    accept = {"Accept": "application/json, text/event-stream"}
    ok = cliente.post("/mcp", json=corpo, headers={**accept, "Host": "localhost:8000"})
    assert ok.status_code == 200 and ok.json()["result"]["tools"]
    # DNS rebinding: um site qualquer apontando para 127.0.0.1 chega com outro Host/Origin.
    assert (
        cliente.post("/mcp", json=corpo, headers={**accept, "Host": "mal.example"}).status_code
        == 403
    )
    origem = {**accept, "Host": "127.0.0.1:8000", "Origin": "https://mal.example"}
    assert cliente.post("/mcp", json=corpo, headers=origem).status_code == 403


def test_listar_divisoes_pagina_com_offset(chamar, db, usuario_a, usuario_b):
    token = ativar_mcp(db, usuario_a)
    for i in range(3):
        chamar(token, "criar_divisao", descricao=f"D{i}", valor=10, participantes=[usuario_b.id])
    r = chamar(token, "listar_divisoes", limite=2)
    assert "Use `offset=2`" in texto(r)
    r = chamar(token, "listar_divisoes", limite=2, offset=2)
    assert len(r["structuredContent"]["itens"]) == 1
    assert "Mostrando 3–3 de 3" in texto(r)
