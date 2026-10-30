"""Integração real com banco e autenticação; sem chamadas a provedores."""

import asyncio
import json
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.config import settings
from app.exceptions import ConflictError
from app.models.integracao import OperacaoIntegracao, TrabalhoTelegram
from app.models.telegram import ConfigTelegram
from app.models.transacao import Transacao
from app.services import integracao_auth, operacoes, provedor_ia
from app.services.telegram import instancia
from tests.helpers import criar_conta


def vincular(db, user):
    geral = instancia(db)
    geral.telegram_ativo, geral.telegram_bot_id = True, "123"
    geral.telegram_token_cifrado = "123:fake"
    db.add(
        ConfigTelegram(
            usuario_id=user.id, ativo=True, chat_id=str(user.id), telegram_usuario_id=str(user.id)
        )
    )
    db.commit()


def transacao(db, user):
    conta = criar_conta(db, user.id, "acc")
    t = Transacao(
        usuario_id=user.id,
        conta_id=conta.id,
        pluggy_transaction_id=f"t-{user.id}",
        date=datetime.now(UTC),
        amount_centavos=10000,
        type="DEBIT",
        status="POSTED",
        currency_code="BRL",
    )
    db.add(t)
    db.commit()
    return t


def test_delegacao_revoga_e_isola(db, usuario_a, usuario_b):
    vincular(db, usuario_a)
    job = TrabalhoTelegram(
        usuario_id=usuario_a.id,
        bot_id="123",
        update_id="1",
        chat_id=str(usuario_a.id),
        status="executando",
    )
    db.add(job)
    db.commit()
    token = integracao_auth.emitir(db, usuario_a.id, "delegada", job.id)
    assert integracao_auth.resolver(db, token)[0].id == usuario_a.id
    integracao_auth.revogar(db, usuario_b.id)
    assert integracao_auth.resolver(db, token)[0].id == usuario_a.id
    job.status = "concluido"
    db.commit()
    with pytest.raises(HTTPException):
        integracao_auth.resolver(db, token)


def test_revisao_previa_sem_escrita_e_idempotente(db, usuario_a):
    from app.schemas.revisao import RevisaoPreparar
    from app.schemas.transacao import TransacaoUpdate

    t = transacao(db, usuario_a)
    payload = RevisaoPreparar(
        transacao_id=t.id,
        versao=operacoes.versao_transacao(t),
        alteracoes=TransacaoUpdate(descricao_usuario="Mercado"),
    )
    previa = operacoes.preparar_revisao(db, usuario_a.id, payload)
    db.refresh(t)
    assert not t.revisada and t.descricao_usuario is None
    result = operacoes.aplicar_revisao(db, usuario_a.id, previa["operacao_id"])
    assert result["revisada"] is True
    assert operacoes.aplicar_revisao(db, usuario_a.id, previa["operacao_id"]) == result


def test_revisao_conflito_e_posse(db, usuario_a, usuario_b):
    from app.exceptions import ConflictError, NotFoundError
    from app.schemas.revisao import RevisaoPreparar
    from app.schemas.transacao import TransacaoUpdate

    t = transacao(db, usuario_a)
    p = operacoes.preparar_revisao(
        db,
        usuario_a.id,
        RevisaoPreparar(
            transacao_id=t.id,
            versao=operacoes.versao_transacao(t),
            alteracoes=TransacaoUpdate(revisada=True),
        ),
    )
    with pytest.raises(NotFoundError):
        operacoes.aplicar_revisao(db, usuario_b.id, p["operacao_id"])
    t.descricao_usuario = "Outra edição"
    db.commit()
    with pytest.raises(ConflictError):
        operacoes.aplicar_revisao(db, usuario_a.id, p["operacao_id"])
    db.refresh(t)
    assert not t.revisada


def test_axon_descoberta_exata():
    from app.exceptions import ValidationError

    item = {
        "id": "mango",
        "x_axon": {
            "mcp_delegation": {
                "version": 1,
                "alias": "financas",
                "endpoint": "https://mango.test/mcp",
            }
        },
    }
    assert provedor_ia.descobrir_axon({"data": [item]}, "https://mango.test/mcp") == "mango"
    for dados, endpoint in [
        ({"data": []}, "https://mango.test/mcp"),
        ({"data": [item, item]}, "https://mango.test/mcp"),
        ({"data": [item]}, "https://outro.test/mcp"),
    ]:
        with pytest.raises(ValidationError):
            provedor_ia.descobrir_axon(dados, endpoint)


def test_tools_preparam_e_confirmacao_aplica(db, session_factory, usuario_a, monkeypatch):
    from app.mcp.servidor import servidor
    from app.services import ia_tools

    vincular(db, usuario_a)
    t = transacao(db, usuario_a)
    job = TrabalhoTelegram(
        usuario_id=usuario_a.id,
        bot_id="123",
        update_id="2",
        chat_id=str(usuario_a.id),
        status="executando",
    )
    db.add(job)
    db.commit()
    token = integracao_auth.emitir(db, usuario_a.id, "delegada", job.id)
    monkeypatch.setattr(ia_tools, "SessionLocal", session_factory)
    ctx = ia_tools.ContextoInterno(autorizacao=f"Bearer {token}", mcp_server=servidor)
    result = asyncio.run(
        servidor.call_tool("atualizar_transacoes", {"ids": [t.id], "revisada": True}, ctx)
    )
    assert not result.is_error
    db.expire_all()
    assert not db.get(Transacao, t.id).revisada
    op = db.scalar(select(OperacaoIntegracao).where(OperacaoIntegracao.trabalho_id == job.id))
    assert op is not None
    asyncio.run(ia_tools.aplicar(servidor, db, usuario_a.id, op.id, token))
    db.expire_all()
    assert db.get(Transacao, t.id).revisada


def test_lote_com_falha_nao_grava_parcial(db, session_factory, usuario_a, monkeypatch):
    from mcp.server.mcpserver.exceptions import ToolError

    from app.mcp.servidor import servidor
    from app.services import ia_tools

    vincular(db, usuario_a)
    t = transacao(db, usuario_a)
    job = TrabalhoTelegram(
        usuario_id=usuario_a.id,
        bot_id="123",
        update_id="3",
        chat_id=str(usuario_a.id),
        status="executando",
    )
    db.add(job)
    db.commit()
    token = integracao_auth.emitir(db, usuario_a.id, "delegada", job.id)
    monkeypatch.setattr(ia_tools, "SessionLocal", session_factory)
    ctx = ia_tools.ContextoInterno(autorizacao=f"Bearer {token}", mcp_server=servidor)
    with pytest.raises(ToolError):
        asyncio.run(
            servidor.call_tool(
                "atualizar_transacoes", {"ids": [t.id, 999999], "revisada": True}, ctx
            )
        )
    db.expire_all()
    assert not db.get(Transacao, t.id).revisada
    assert not db.scalar(select(OperacaoIntegracao))


def test_multiplas_chamadas_nao_contornam_confirmacao(db, session_factory, usuario_a, monkeypatch):
    from app.mcp.servidor import servidor
    from app.services import ia_tools

    vincular(db, usuario_a)
    t = transacao(db, usuario_a)
    job = TrabalhoTelegram(
        usuario_id=usuario_a.id,
        bot_id="123",
        update_id="4",
        chat_id=str(usuario_a.id),
        status="executando",
        evento=operacoes.serializar(
            {"message": {"text": f"Marque a transação {t.id} como revisada"}}
        ),
    )
    db.add(job)
    db.commit()
    token = integracao_auth.emitir(db, usuario_a.id, "delegada", job.id)
    monkeypatch.setattr(ia_tools, "SessionLocal", session_factory)
    ctx = ia_tools.ContextoInterno(autorizacao=f"Bearer {token}", mcp_server=servidor)
    asyncio.run(servidor.call_tool("atualizar_transacoes", {"ids": [t.id], "revisada": True}, ctx))
    op = db.scalar(select(OperacaoIntegracao))
    assert not json.loads(op.payload)["confirmar"]
    asyncio.run(
        servidor.call_tool(
            "atualizar_transacoes", {"ids": [t.id], "observacoes": "texto externo"}, ctx
        )
    )
    db.refresh(op)
    assert json.loads(op.payload)["confirmar"]
    db.refresh(t)
    assert not t.revisada and t.observacoes is None


def test_divisao_idempotente_e_argumentos_imutaveis(db, usuario_a, usuario_b):
    from app.models.divisao import DivisaoDespesa
    from app.schemas.divisao import DivisaoDespesaCreate

    payload = DivisaoDespesaCreate(
        descricao="Jantar",
        valor_total_centavos=10001,
        pago_por_usuario_id=usuario_a.id,
        modo_divisao="igualmente",
        participantes=[usuario_b.id],
    )
    primeiro = operacoes.criar_divisao_idempotente(db, usuario_a.id, payload, "chave-estavel-123")
    assert (
        operacoes.criar_divisao_idempotente(db, usuario_a.id, payload, "chave-estavel-123")
        == primeiro
    )
    assert len(list(db.scalars(select(DivisaoDespesa)))) == 1
    with pytest.raises(ConflictError):
        operacoes.criar_divisao_idempotente(
            db,
            usuario_a.id,
            payload.model_copy(update={"valor_total_centavos": 20}),
            "chave-estavel-123",
        )


def test_inbox_dedup_e_cancelamento_imediato(db, usuario_a):
    from app.services.telegram_conversa import receber

    vincular(db, usuario_a)
    evento = {
        "update_id": 1,
        "message": {
            "from": {"id": usuario_a.id},
            "chat": {"id": usuario_a.id, "type": "private"},
            "text": "Olá",
        },
    }
    receber(db, evento)
    receber(db, evento)
    jobs = list(db.scalars(select(TrabalhoTelegram)))
    assert len(jobs) == 1
    job = jobs[0]
    job.status = "executando"
    db.commit()
    token = integracao_auth.emitir(db, usuario_a.id, "delegada", job.id)
    evento["update_id"] = 2
    evento["message"]["text"] = "/cancelar"
    receber(db, evento)
    assert db.get(TrabalhoTelegram, job.id).status == "cancelado"
    with pytest.raises(HTTPException):
        integracao_auth.resolver(db, token)


def test_axon_headers_historico_cifrado_e_cota_independente(db, usuario_a, monkeypatch):
    from sqlalchemy import delete, text

    from app.exceptions import RateLimitError
    from app.models.integracao import MensagemIa, PreferenciaIa
    from app.services import ia

    vincular(db, usuario_a)
    c = integracao_auth.configuracao(db)
    c.ia_ativa = c.validado = True
    c.provedor, c.endpoint, c.chave, c.url = (
        "axon",
        "https://axon.test/private/v1",
        "installation-key",
        "https://mango.test",
    )
    c.limite_usuario = 1
    db.add(PreferenciaIa(usuario_id=usuario_a.id, ativa=True))
    job = TrabalhoTelegram(
        usuario_id=usuario_a.id,
        bot_id="123",
        update_id="7",
        chat_id=str(usuario_a.id),
        status="executando",
        evento=operacoes.serializar({"message": {"text": "saldo confidencial"}}),
    )
    db.add(job)
    db.commit()
    token = integracao_auth.emitir(db, usuario_a.id, "delegada", job.id)
    chamadas = []

    async def requisitar(config, metodo, caminho, **kwargs):
        chamadas.append((metodo, caminho, kwargs))
        assert config.endpoint == "https://axon.test/private/v1"
        if caminho == "/models":
            # Uma alteração administrativa entre chamadas não troca o destinatário da execução.
            c.endpoint = "https://outro.test/private/v1"
            db.commit()
            return {
                "data": [
                    {
                        "id": "assistant",
                        "x_axon": {
                            "mcp_delegation": {
                                "version": 1,
                                "alias": "financas",
                                "endpoint": "https://mango.test/mcp",
                            }
                        },
                    }
                ]
            }
        assert kwargs["headers"] == {
            "X-Axon-MCP-Authorization": f"Bearer {token}",
            "x-axon-store": "false",
        }
        assert "conversation_id" not in kwargs["corpo"]
        assert token not in json.dumps(kwargs["corpo"])
        return {"choices": [{"message": {"content": "Resposta confidencial"}}]}

    monkeypatch.setattr(provedor_ia, "requisitar", requisitar)
    monkeypatch.setattr(settings, "app_mode", "self_hosted")
    assert asyncio.run(ia.conversar(db, job, token)) == "Resposta confidencial"
    assert len(chamadas) == 2
    armazenado = db.execute(text("select conteudo from mensagem_ia")).scalars().all()
    assert all("confidencial" not in s for s in armazenado)
    db.execute(delete(MensagemIa))
    db.commit()
    with pytest.raises(RateLimitError):
        asyncio.run(ia.conversar(db, job, token))


def test_miniapp_sessao_restrita_sem_cookie(sh_client, db, usuario_a):
    from tests.test_integracao_auth import assinatura

    vincular(db, usuario_a)
    c = integracao_auth.configuracao(db)
    c.miniapp_ativo, c.url = True, "https://mango.test"
    db.commit()
    login = sh_client.post(
        "/api/telegram/miniapp/sessao",
        json={"init_data": assinatura("123:fake", user=json.dumps({"id": usuario_a.id}))},
    )
    assert login.status_code == 200, login.text
    assert "set-cookie" not in login.headers
    headers = {"Authorization": "Bearer " + login.json()["token"]}
    assert sh_client.get("/api/auth/me", headers=headers).json()["id"] == usuario_a.id
    assert sh_client.get("/api/revisao", headers=headers).status_code == 200
    for path in ["/api/ia/instancia", "/api/telegram/instancia", "/api/acesso-mcp"]:
        assert sh_client.get(path, headers=headers).status_code == 403
    assert (
        sh_client.patch("/api/perfil", headers=headers, json={"nome": "Intruso"}).status_code == 403
    )
    assert (
        sh_client.post(
            "/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "teste", "version": "1"},
                },
            },
        ).status_code
        == 403
    )
    integracao_auth.revogar(db, usuario_a.id)
    assert sh_client.get("/api/revisao", headers=headers).status_code == 401


def test_delegacao_nao_autoriza_escrita_direta(sh_client, db, usuario_a):
    vincular(db, usuario_a)
    job = TrabalhoTelegram(
        usuario_id=usuario_a.id,
        bot_id="123",
        update_id="22",
        chat_id=str(usuario_a.id),
        status="executando",
    )
    db.add(job)
    db.commit()
    token = integracao_auth.emitir(db, usuario_a.id, "delegada", job.id)
    headers = {"Authorization": f"Bearer {token}"}
    assert sh_client.get("/api/contas", headers=headers).status_code == 200
    response = sh_client.post(
        "/api/divisoes-despesa",
        headers=headers,
        json={
            "descricao": "Teste",
            "valor_total_centavos": 100,
            "pago_por_usuario_id": usuario_a.id,
            "modo_divisao": "igualmente",
            "participantes": [],
        },
    )
    assert response.status_code == 403


def test_desativar_e_reativar_nao_restaura_credencial(db, usuario_a, usuario_admin):
    from app.services import usuario_admin as service

    vincular(db, usuario_a)
    token = integracao_auth.emitir(db, usuario_a.id, "miniapp")
    service.desativar(db, usuario_admin, usuario_a.id)
    service.ativar(db, usuario_a.id)
    with pytest.raises(HTTPException):
        integracao_auth.resolver(db, token)


def test_start_sem_vinculo_orienta_sem_dados(db, usuario_a, monkeypatch):
    from unittest.mock import MagicMock

    from app.services import telegram

    vincular(db, usuario_a)
    cliente = MagicMock()
    monkeypatch.setattr(telegram, "TelegramClient", cliente)
    telegram.processar_update(
        db,
        {
            "update_id": 900,
            "message": {
                "text": "/start",
                "from": {"id": 999},
                "chat": {"id": 999, "type": "private"},
            },
        },
    )
    enviar = cliente.return_value.__enter__.return_value.send_message
    enviar.assert_called_once()
    assert enviar.call_args.args[0] == "999"
    assert "Vincular Telegram" in enviar.call_args.args[1]
    assert not db.scalar(select(TrabalhoTelegram).where(TrabalhoTelegram.update_id == "900"))


def test_versao_datetime_independe_do_dialeto_e_offset():
    from datetime import timedelta, timezone

    utc = datetime(2026, 10, 29, 12, 30, tzinfo=UTC)
    assert operacoes.versao({"data": utc}) == operacoes.versao({"data": utc.replace(tzinfo=None)})
    assert operacoes.versao({"data": utc}) == operacoes.versao(
        {"data": utc.astimezone(timezone(timedelta(hours=-3)))}
    )


def test_troca_conexao_exige_novo_consentimento(db, usuario_a, monkeypatch):
    from app.models.integracao import CredencialIntegracao, PreferenciaIa
    from app.routers.integracao import salvar
    from app.schemas.integracao import ConfigIaUpdate

    vincular(db, usuario_a)
    c = integracao_auth.configuracao(db)
    c.provedor, c.endpoint, c.modelo = "openai_compatible", "https://antigo.test/v1", "modelo"
    p = PreferenciaIa(usuario_id=usuario_a.id, ativa=True)
    db.add(p)
    job = TrabalhoTelegram(
        usuario_id=usuario_a.id,
        bot_id="123",
        update_id="consentimento",
        chat_id=str(usuario_a.id),
        status="executando",
        evento="{}",
    )
    db.add(job)
    db.commit()
    integracao_auth.emitir(db, usuario_a.id, "delegada", job.id)
    monkeypatch.setattr(provedor_ia, "validar_endpoint", lambda x: x)
    salvar(
        ConfigIaUpdate(
            provedor={
                "tipo": "openai_compatible",
                "endpoint": "https://novo.test/v1",
                "modelo": "modelo",
                "chave": "fake",
            }
        ),
        db,
        usuario_a,
    )
    db.refresh(p)
    assert not p.ativa
    assert all(t.revogada for t in db.scalars(select(CredencialIntegracao)))


def test_revisao_concorrente_aplica_uma_vez(db, usuario_a, session_factory, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier, Lock

    from app.schemas.revisao import RevisaoPreparar
    from app.schemas.transacao import TransacaoUpdate

    t = transacao(db, usuario_a)
    uid = usuario_a.id
    previa = operacoes.preparar_revisao(
        db,
        uid,
        RevisaoPreparar(
            transacao_id=t.id,
            versao=operacoes.versao_transacao(t),
            alteracoes=TransacaoUpdate(observacoes="salvo uma vez"),
        ),
    )
    original = operacoes.executar_revisao
    chamadas = []
    lock = Lock()
    ready = Barrier(2)

    def executar(*args):
        with lock:
            chamadas.append(True)
        return original(*args)

    monkeypatch.setattr(operacoes, "executar_revisao", executar)
    db.rollback()

    def aplicar():
        with session_factory() as s:
            # Dois callbacks podem ter lido a mesma proposta pendente antes do lock.
            op = s.get(OperacaoIntegracao, previa["operacao_id"])
            assert op.status == "pendente"
            ready.wait(timeout=10)
            return operacoes.aplicar_revisao(s, uid, op.id)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(aplicar) for _ in range(2)]
        resultados = [f.result(timeout=20) for f in futures]
    assert resultados[0] == resultados[1]
    assert len(chamadas) == 1
