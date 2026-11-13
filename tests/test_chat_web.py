"""Chat web (docs/dev/chat-web.md): provedor simulado, banco e credenciais reais."""

import asyncio
import json
import queue
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import select, text, update
from starlette.requests import Request

from app.exceptions import ConflictError, NotFoundError, RateLimitError
from app.models.integracao import (
    ConversaIa,
    CredencialIntegracao,
    MensagemIa,
    PreferenciaIa,
)
from app.models.transacao import Transacao
from app.services import chat_web, ia_tools, integracao_auth, provedor_ia
from tests.test_integracao_v2 import transacao

_ASYNC_CLIENT = httpx.AsyncClient  # antes de qualquer monkeypatch


@pytest.fixture(autouse=True)
def _isolar(session_factory, monkeypatch):
    monkeypatch.setattr(chat_web, "SessionLocal", session_factory)
    monkeypatch.setattr(ia_tools, "SessionLocal", session_factory)

    async def testar(config):
        return "assistant"

    monkeypatch.setattr(provedor_ia, "testar", testar)
    chat_web._execucoes.clear()
    yield
    chat_web._execucoes.clear()


def ativar(db, *users, limite=50):
    c = integracao_auth.configuracao(db)
    c.ia_ativa = c.validado = True
    c.provedor, c.endpoint, c.chave, c.url = (
        "axon",
        "https://axon.test/private/v1",
        "installation-key",
        "https://mango.test",
    )
    c.limite_usuario = limite
    for user in users:
        db.add(PreferenciaIa(usuario_id=user.id, ativa=True))
    db.commit()


def falso(monkeypatch, *deltas, antes=None):
    """`transmitir` simulado; `antes(token, corpo)` roda como se o Axon chamasse o MCP."""
    chamadas = []

    async def transmitir(config, caminho, *, corpo, headers=None):
        chamadas.append({"caminho": caminho, "corpo": corpo, "headers": headers})
        token = headers["X-Axon-MCP-Authorization"].split(" ", 1)[1]
        if antes:
            await antes(token, corpo)
        for d in deltas:
            yield d

    monkeypatch.setattr(provedor_ia, "transmitir", transmitir)
    return chamadas


def eventos_sse(corpo: str):
    saida = []
    for bloco in corpo.split("\n\n"):
        linhas = [linha for linha in bloco.split("\n") if linha and not linha.startswith(":")]
        if not linhas:
            continue
        tipo = linhas[0].removeprefix("event: ")
        saida.append((tipo, json.loads(linhas[1].removeprefix("data: "))))
    return saida


def drenar(fila: queue.Queue):
    saida = []
    while (item := fila.get(timeout=10)) is not None:
        saida.append(item)
    return saida


def test_stream_axon_persiste_cifrado_e_revoga(client_factory, db, usuario_a, monkeypatch):
    ativar(db, usuario_a)
    chamadas = falso(monkeypatch, "Gastou ", "R$ 10 confidencial")
    cliente = client_factory(usuario_a)
    r = cliente.post("/api/ia/mensagens", json={"texto": "quanto gastei?"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    eventos = eventos_sse(r.text)
    tipos = [t for t, _ in eventos]
    assert tipos[0] == "conversa" and tipos[-1] == "fim"
    assert "".join(d["texto"] for t, d in eventos if t == "delta") == "Gastou R$ 10 confidencial"
    conversa_id = eventos[0][1]["id"]
    assert eventos[0][1]["titulo"] == "quanto gastei?"
    assert db.get(MensagemIa, eventos[0][1]["pedido_id"]).conteudo == "quanto gastei?"

    (chamada,) = chamadas
    assert chamada["corpo"]["stream"] is True and chamada["corpo"]["model"] == "assistant"
    assert chamada["headers"]["x-axon-store"] == "false"
    token = chamada["headers"]["X-Axon-MCP-Authorization"].split(" ", 1)[1]
    assert token.startswith("mgi_") and token not in json.dumps(chamada["corpo"])
    assert chamada["corpo"]["messages"][0]["role"] == "system"
    assert chamada["corpo"]["messages"][-1] == {"role": "user", "content": "quanto gastei?"}

    armazenado = db.execute(text("select conteudo from mensagem_ia")).scalars().all()
    assert len(armazenado) == 2 and all("confidencial" not in s for s in armazenado)
    with pytest.raises(HTTPException):
        integracao_auth.resolver(db, token)

    detalhe = cliente.get(f"/api/ia/conversas/{conversa_id}").json()
    assert [m["papel"] for m in detalhe["mensagens"]] == ["user", "assistant"]
    assert detalhe["mensagens"][1]["conteudo"] == "Gastou R$ 10 confidencial"
    assert detalhe["executando"] is False and detalhe["proposta"] is None


def test_erro_do_provedor_nao_persiste_resposta(client_factory, db, usuario_a, monkeypatch):
    from app.exceptions import UpstreamError

    ativar(db, usuario_a)

    async def transmitir(config, caminho, *, corpo, headers=None):
        raise UpstreamError("limite do provedor atingido")
        yield  # pragma: no cover

    monkeypatch.setattr(provedor_ia, "transmitir", transmitir)
    eventos = eventos_sse(
        client_factory(usuario_a).post("/api/ia/mensagens", json={"texto": "oi"}).text
    )
    assert eventos[-1] == ("erro", {"mensagem": "limite do provedor atingido"})
    papeis = db.scalars(select(MensagemIa.papel)).all()
    assert papeis == ["user"]


def test_credencial_web_sem_telegram_e_revogacao(db, usuario_a):
    ativar(db, usuario_a)
    conversa = ConversaIa(usuario_id=usuario_a.id, titulo="t")
    db.add(conversa)
    db.flush()
    pedido = MensagemIa(
        usuario_id=usuario_a.id, conversa_id=conversa.id, papel="user", conteudo="x"
    )
    db.add(pedido)
    db.commit()
    token = integracao_auth.emitir(db, usuario_a.id, "web", mensagem_id=pedido.id)
    user, cred = integracao_auth.resolver(db, token)
    assert user.id == usuario_a.id and cred.bot_id is None

    escrita = Request(
        {"type": "http", "method": "PATCH", "path": "/api/transacoes/1", "headers": []}
    )
    with pytest.raises(HTTPException) as exc:
        integracao_auth.autorizar_rota(escrita, cred, user)
    assert exc.value.status_code == 403

    db.execute(update(PreferenciaIa).values(ativa=False))
    db.commit()
    with pytest.raises(HTTPException):
        integracao_auth.resolver(db, token)
    db.execute(update(PreferenciaIa).values(ativa=True))
    integracao_auth.configuracao(db).ia_ativa = False
    db.commit()
    with pytest.raises(HTTPException):
        integracao_auth.resolver(db, token)


def test_isolamento_entre_usuarios(client_factory, db, usuario_a, usuario_b, monkeypatch):
    ativar(db, usuario_a, usuario_b)
    falso(monkeypatch, "ok")
    a, b = client_factory(usuario_a), client_factory(usuario_b)
    conversa_id = eventos_sse(a.post("/api/ia/mensagens", json={"texto": "segredo"}).text)[0][1][
        "id"
    ]
    assert b.get("/api/ia/conversas").json() == []
    assert b.get(f"/api/ia/conversas/{conversa_id}").status_code == 404
    assert b.patch(f"/api/ia/conversas/{conversa_id}", json={"titulo": "x"}).status_code == 404
    assert b.delete(f"/api/ia/conversas/{conversa_id}").status_code == 404
    r = b.post("/api/ia/mensagens", json={"conversa_id": conversa_id, "texto": "oi"})
    assert r.status_code == 404
    r = b.post("/api/ia/mensagens", json={"conversa_id": conversa_id, "regenerar": True})
    assert r.status_code == 404

    assert a.patch(f"/api/ia/conversas/{conversa_id}", json={"titulo": "Novo"}).status_code == 200
    assert a.get("/api/ia/conversas").json()[0]["titulo"] == "Novo"
    assert a.delete(f"/api/ia/conversas/{conversa_id}").status_code == 204
    assert not db.scalars(select(MensagemIa)).all()


def test_cota_regenerar_consome_e_apagar_nao_devolve(client_factory, db, usuario_a, monkeypatch):
    ativar(db, usuario_a, limite=2)
    chamadas = falso(monkeypatch, "resposta")
    cliente = client_factory(usuario_a)
    conversa_id = eventos_sse(cliente.post("/api/ia/mensagens", json={"texto": "a"}).text)[0][1][
        "id"
    ]
    r = cliente.post("/api/ia/mensagens", json={"conversa_id": conversa_id, "regenerar": True})
    assert eventos_sse(r.text)[-1][0] == "fim"
    # Regenerar substitui a resposta e reaproveita o pedido.
    assert db.scalars(select(MensagemIa.papel).order_by(MensagemIa.id)).all() == [
        "user",
        "assistant",
    ]
    assert chamadas[1]["corpo"]["messages"][-1] == {"role": "user", "content": "a"}
    cliente.delete(f"/api/ia/conversas/{conversa_id}")
    assert cliente.post("/api/ia/mensagens", json={"texto": "b"}).status_code == 429
    assert not db.scalars(select(ConversaIa)).all()


def test_execucao_unica_e_parar(db, usuario_a, monkeypatch):
    ativar(db, usuario_a)

    async def transmitir(config, caminho, *, corpo, headers=None):
        yield "parcial"
        await asyncio.sleep(30)
        yield "nunca"

    monkeypatch.setattr(provedor_ia, "transmitir", transmitir)
    conversa, _, fila = chat_web.iniciar(db, usuario_a.id, None, "longo", False)
    assert fila.get(timeout=5)[0] == "status"
    assert fila.get(timeout=5) == ("delta", {"texto": "parcial"})
    with pytest.raises(ConflictError):
        chat_web.iniciar(db, usuario_a.id, conversa.id, "outro", False)
    assert chat_web.executando(usuario_a.id, conversa.id)
    chat_web.parar(db, usuario_a.id)
    (fim,) = drenar(fila)
    assert fim[0] == "fim" and fim[1]["mensagem_id"]
    db.expire_all()
    assert db.get(MensagemIa, fim[1]["mensagem_id"]).conteudo == "parcial"
    assert all(c.revogada for c in db.scalars(select(CredencialIntegracao)))
    assert not chat_web.executando(usuario_a.id)


def _preparar_escrita(t):
    from app.mcp.servidor import servidor

    async def antes(token, corpo):
        ctx = ia_tools.ContextoInterno(autorizacao=f"Bearer {token}", mcp_server=servidor)
        await servidor.call_tool("atualizar_transacoes", {"ids": [t.id], "revisada": True}, ctx)

    return antes


def test_proposta_web_confirma_uma_vez(db, usuario_a, monkeypatch):
    ativar(db, usuario_a)
    t = transacao(db, usuario_a)
    falso(monkeypatch, "Preparei a alteração.", antes=_preparar_escrita(t))
    conversa, _, fila = chat_web.iniciar(db, usuario_a.id, None, "revise a última compra", False)
    eventos = dict(drenar(fila))
    proposta = eventos["proposta"]
    assert "Editar transações" in proposta["resumo"]
    db.expire_all()
    assert not db.get(Transacao, t.id).revisada
    pendente = chat_web.proposta_pendente(db, usuario_a.id, conversa.id)
    assert pendente.id == proposta["operacao_id"]

    # Outra confirmação em paralelo: a credencial dela não pode ser revogada por esta.
    paralela = integracao_auth.emitir(
        db, usuario_a.id, "web_confirma", mensagem_id=pendente.mensagem_id
    )
    asyncio.run(chat_web.confirmar(db, usuario_a.id, proposta["operacao_id"]))
    db.expire_all()
    assert db.get(Transacao, t.id).revisada
    integracao_auth.resolver(db, paralela)
    with pytest.raises(NotFoundError):
        asyncio.run(chat_web.confirmar(db, usuario_a.id, proposta["operacao_id"]))
    # Confirmar não consome cota (credencial própria) e o resultado entra na conversa.
    tipos = db.scalars(select(CredencialIntegracao.tipo)).all()
    assert sorted(tipos) == ["web", "web_confirma", "web_confirma"]
    assert db.scalars(
        select(MensagemIa.papel).where(MensagemIa.conversa_id == conversa.id)
    ).all() == ["user", "assistant", "assistant"]


def test_frase_exata_aplica_sem_botao(db, usuario_a, monkeypatch):
    ativar(db, usuario_a)
    t = transacao(db, usuario_a)
    falso(monkeypatch, "Feito.", antes=_preparar_escrita(t))
    _, _, fila = chat_web.iniciar(
        db, usuario_a.id, None, f"Marque a transação {t.id} como revisada", False
    )
    eventos = dict(drenar(fila))
    assert "aplicada" in eventos and "proposta" not in eventos
    db.expire_all()
    assert db.get(Transacao, t.id).revisada


def test_contexto_por_conversa_e_retencao(db, usuario_a, monkeypatch):
    ativar(db, usuario_a)
    chamadas = falso(monkeypatch, "ok")
    c1, _, fila = chat_web.iniciar(db, usuario_a.id, None, "primeira conversa", False)
    c1_id = c1.id
    drenar(fila)
    _, _, fila = chat_web.iniciar(db, usuario_a.id, None, "segunda conversa", False)
    drenar(fila)
    conteudos = json.dumps(chamadas[1]["corpo"]["messages"], ensure_ascii=False)
    assert "primeira conversa" not in conteudos

    antigo = datetime.now(UTC) - timedelta(days=8)
    db.execute(update(MensagemIa).where(MensagemIa.conversa_id == c1_id).values(criado_em=antigo))
    db.execute(update(ConversaIa).where(ConversaIa.id == c1_id).values(atualizado_em=antigo))
    db.commit()
    chat_web.limpar(db)
    assert db.get(ConversaIa, c1_id) is None
    assert len(db.scalars(select(ConversaIa)).all()) == 1


def test_ia_indisponivel_e_cota_soma_telegram(db, usuario_a, monkeypatch):
    from app.models.integracao import TrabalhoTelegram

    with pytest.raises(ConflictError):
        chat_web.iniciar(db, usuario_a.id, None, "oi", False)
    ativar(db, usuario_a, limite=1)
    db.add(
        TrabalhoTelegram(
            usuario_id=usuario_a.id, bot_id="1", update_id="1", chat_id="1", ia_aceita=True
        )
    )
    db.commit()
    falso(monkeypatch, "ok")
    with pytest.raises(RateLimitError):
        chat_web.iniciar(db, usuario_a.id, None, "oi", False)
    assert not db.scalars(select(MensagemIa)).all()
    assert not chat_web.executando(usuario_a.id)


def _stream(monkeypatch, *blocos: bytes):
    """`transmitir` real contra um transporte HTTP simulado que entrega `blocos` em sequência."""
    import httpx

    async def corpo():
        for b in blocos:
            yield b

    def handler(request):
        return httpx.Response(200, content=corpo())

    monkeypatch.setattr(provedor_ia, "validar_endpoint", lambda v: v)
    monkeypatch.setattr(
        provedor_ia.httpx,
        "AsyncClient",
        lambda **kw: _ASYNC_CLIENT(transport=httpx.MockTransport(handler), **kw),
    )
    config = type("C", (), {"endpoint": "https://axon.test/v1", "chave": "k", "provedor": "axon"})

    async def ler():
        return [d async for d in provedor_ia.transmitir(config, "/chat/completions", corpo={})]

    return ler


def test_transmitir_exige_done_e_limita_linha(monkeypatch):
    from app.exceptions import UpstreamError

    delta = b'data: {"choices": [{"delta": {"content": "ol\xc3'
    # Evento e caractere UTF-8 partidos entre blocos; CRLF aceito.
    ler = _stream(monkeypatch, delta, b'\xa1"}}]}\r\n\r\n', b"data: [DONE]\n\n")
    assert asyncio.run(ler()) == ["olá"]

    # Conexão encerrada sem [DONE]: resposta incompleta não vira texto salvo.
    ler = _stream(monkeypatch, b'data: {"choices": [{"delta": {"content": "x"}}]}\n\n')
    with pytest.raises(UpstreamError, match="interrompida"):
        asyncio.run(ler())

    gigante = b"data: " + b"a" * (provedor_ia.LINHA_MAX + 10)
    for blocos in ((gigante,), (gigante + b"\n\ndata: [DONE]\n\n",)):
        ler = _stream(monkeypatch, *blocos)
        with pytest.raises(UpstreamError):
            asyncio.run(ler())


def test_limpar_e_cancelar_do_telegram_preservam_o_chat_web(db, usuario_a, monkeypatch):
    from app.models.integracao import OperacaoIntegracao, TrabalhoTelegram
    from app.services import operacoes, telegram_conversa
    from tests.test_integracao_v2 import vincular

    ativar(db, usuario_a)
    vincular(db, usuario_a)
    conversa = ConversaIa(usuario_id=usuario_a.id, titulo="web")
    db.add(conversa)
    db.flush()
    pedido = MensagemIa(
        usuario_id=usuario_a.id, conversa_id=conversa.id, papel="user", conteudo="web"
    )
    db.add(pedido)
    db.flush()
    db.add(
        OperacaoIntegracao(
            id="op-web",
            usuario_id=usuario_a.id,
            mensagem_id=pedido.id,
            tipo="ia",
            status="pendente",
            payload="{}",
            expira_em=datetime.now(UTC) + timedelta(minutes=10),
        )
    )
    job = TrabalhoTelegram(
        usuario_id=usuario_a.id, bot_id="123", update_id="1", chat_id=str(usuario_a.id)
    )
    db.add(job)
    db.flush()
    db.add(MensagemIa(usuario_id=usuario_a.id, trabalho_id=job.id, papel="user", conteudo="tg"))
    db.add(
        OperacaoIntegracao(
            id="op-limpar",
            usuario_id=usuario_a.id,
            trabalho_id=job.id,
            tipo="limpar",
            status="pendente",
            payload="{}",
            expira_em=datetime.now(UTC) + timedelta(minutes=10),
        )
    )
    db.commit()
    web = integracao_auth.emitir(db, usuario_a.id, "web", mensagem_id=pedido.id)
    job.evento = operacoes.serializar({"callback_query": {"id": "cb", "data": "sim:op-limpar"}})
    db.commit()

    class Cliente:
        def callback(self, _id):
            pass

    asyncio.run(telegram_conversa.executar(db, job, Cliente()))
    db.expire_all()
    assert db.scalars(select(MensagemIa.conteudo)).all() == ["web"]
    assert db.get(OperacaoIntegracao, "op-web").status == "pendente"
    integracao_auth.resolver(db, web)  # credencial do chat no app segue válida


def test_chave_de_idempotencia_nao_duplica_pedido_nem_cota(
    client_factory, db, usuario_a, monkeypatch
):
    ativar(db, usuario_a)
    chamadas = falso(monkeypatch, "resposta")
    cliente = client_factory(usuario_a)
    corpo = {"texto": "quanto gastei?", "chave": "envio-123456"}
    primeiro = eventos_sse(cliente.post("/api/ia/mensagens", json=corpo).text)
    # Retry do mesmo envio (a resposta HTTP se perdeu): nada novo é gravado nem cobrado.
    segundo = eventos_sse(cliente.post("/api/ia/mensagens", json=corpo).text)
    assert [t for t, _ in segundo] == ["conversa", "fim"]
    assert segundo[0][1]["pedido_id"] == primeiro[0][1]["pedido_id"]
    assert len(chamadas) == 1
    assert db.scalars(select(MensagemIa.papel)).all() == ["user", "assistant"]
    assert len(db.scalars(select(CredencialIntegracao)).all()) == 1

    # Pedido gravado cuja execução morreu sem resposta: o retry gera a resposta desse pedido.
    conversa_id = primeiro[0][1]["id"]
    db.add(
        MensagemIa(
            usuario_id=usuario_a.id,
            conversa_id=conversa_id,
            papel="user",
            conteudo="e o mês passado?",
            chave="envio-abcdefgh",
        )
    )
    db.commit()
    corpo = {"conversa_id": conversa_id, "texto": "e o mês passado?", "chave": "envio-abcdefgh"}
    eventos = eventos_sse(cliente.post("/api/ia/mensagens", json=corpo).text)
    assert eventos[-1][0] == "fim" and len(chamadas) == 2
    assert chamadas[1]["corpo"]["messages"][-1]["content"] == "e o mês passado?"
    assert db.scalars(select(MensagemIa.papel).order_by(MensagemIa.id)).all() == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]
