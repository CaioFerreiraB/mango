"""Inbox durável; dois consumidores, ordem por usuário e polling independente da IA."""

import asyncio
import json
import logging
import secrets
import threading
import time
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, update

from app.config import settings
from app.db.session import SessionLocal
from app.models.integracao import MensagemIa, OperacaoIntegracao, TrabalhoTelegram
from app.models.telegram import ConfigTelegram
from app.models.usuario import Usuario
from app.services.integracao_auth import configuracao, emitir, revogar
from app.services.operacoes import serializar
from app.telegram_client import TelegramClient, TelegramError

_parar = threading.Event()
_threads = []
_claim = threading.Lock()
logger = logging.getLogger("app.telegram.conversa")


def receber(db, evento):
    from app.services.telegram import instancia

    callback = evento.get("callback_query")
    mensagem = callback.get("message") if isinstance(callback, dict) else evento.get("message")
    pessoa = callback.get("from") if isinstance(callback, dict) else (mensagem or {}).get("from")
    if not isinstance(mensagem, dict) or not isinstance(pessoa, dict):
        return
    chat = mensagem.get("chat", {})
    uid = pessoa.get("id")
    if (
        chat.get("type") != "private"
        or type(uid) is not int
        or not 0 < uid < 2**63
        or chat.get("id") != uid
        or pessoa.get("is_bot")
    ):
        return
    if not callback and (
        not isinstance(mensagem.get("text"), str) or len(mensagem["text"]) > 16000
    ):
        return
    vinculo = db.scalar(
        select(ConfigTelegram).where(
            ConfigTelegram.telegram_usuario_id == str(uid), ConfigTelegram.ativo.is_(True)
        )
    )
    if not vinculo:
        return
    geral = instancia(db)
    identificador = evento.get("update_id")
    if type(identificador) is not int:
        return
    if db.scalar(
        select(TrabalhoTelegram.id).where(
            TrabalhoTelegram.bot_id == geral.telegram_bot_id,
            TrabalhoTelegram.update_id == str(identificador),
        )
    ):
        return
    job = TrabalhoTelegram(
        usuario_id=vinculo.usuario_id,
        bot_id=geral.telegram_bot_id,
        update_id=str(identificador),
        chat_id=str(uid),
        evento=serializar(evento),
    )
    db.add(job)
    db.commit()
    # Cancelamento não aguarda a chamada de IA que está em andamento.
    if not callback and mensagem["text"].strip().split(" ")[0].split("@")[0].lower() == "/cancelar":
        cancelar(db, vinculo.usuario_id, job.id)


def cancelar(db, usuario_id, atual):
    db.execute(
        update(OperacaoIntegracao)
        .where(
            OperacaoIntegracao.usuario_id == usuario_id,
            OperacaoIntegracao.status.in_(["preparando", "pendente"]),
        )
        .values(status="cancelada")
    )
    db.execute(
        update(TrabalhoTelegram)
        .where(
            TrabalhoTelegram.usuario_id == usuario_id,
            TrabalhoTelegram.id != atual,
            TrabalhoTelegram.status.in_(["pendente", "executando"]),
        )
        .values(status="cancelado")
    )
    db.commit()
    revogar(db, usuario_id)


def botao_miniapp(c, texto, caminho):
    if settings.app_mode == "self_hosted" and c.miniapp_ativo and c.url:
        return [[{"text": texto, "web_app": {"url": c.url + caminho}}]]
    return None


async def executar(db, job, cliente):
    from app.mcp.servidor import servidor
    from app.security.current_user import _aware
    from app.services import ia, ia_tools, rotina_diaria

    user = db.get(Usuario, job.usuario_id)
    c = configuracao(db)
    evento = json.loads(job.evento)
    callback = evento.get("callback_query")
    if callback:
        cliente.callback(callback["id"])
        data = callback.get("data", "")
        acao, _, op_id = data.partition(":")
        op = db.get(OperacaoIntegracao, op_id)
        if (
            not op
            or op.usuario_id != user.id
            or op.status != "pendente"
            or _aware(op.expira_em) <= datetime.now(UTC)
        ):
            return "Esta confirmação expirou ou já foi utilizada.", None
        if acao == "nao":
            op.status = "cancelada"
            db.commit()
            return "Operação cancelada.", None
        if acao != "sim":
            return "Ação inválida.", None
        if op.tipo == "limpar":
            cancelar(db, user.id, job.id)
            db.execute(delete(MensagemIa).where(MensagemIa.usuario_id == user.id))
            op.status = "concluida"
            db.commit()
            return (
                "Histórico do Mango apagado. "
                "Mensagens no Telegram e registros do provedor permanecem.",
                None,
            )
        token = emitir(db, user.id, "delegada", job.id)
        return await ia_tools.aplicar(servidor, db, user.id, op.id, token), None
    texto = evento["message"]["text"].strip()
    comando = texto.split(" ")[0].split("@")[0].lower()
    if comando == "/cancelar":
        cancelar(db, user.id, job.id)
        return "Trabalho pendente cancelado. Alterações já concluídas permanecem salvas.", None
    if comando == "/limpar":
        op = OperacaoIntegracao(
            id=secrets.token_urlsafe(24),
            usuario_id=user.id,
            trabalho_id=job.id,
            tipo="limpar",
            payload="{}",
            expira_em=datetime.now(UTC) + timedelta(minutes=10),
        )
        db.add(op)
        db.commit()
        return "Apagar o histórico de IA guardado no Mango?", confirmacao(op.id)
    if comando in {"/start", "/ajuda"}:
        texto = (
            "/split — criar divisão\n/divisoes — saldos\n"
            "/cancelar — cancelar pendências\n/limpar — apagar histórico"
        )
        if user.tipo == "completo":
            texto += (
                "\n/revisar — transações pendentes\n/resumo — resumo do mês\n"
                "Envie uma mensagem para conversar com a IA configurada."
            )
        return texto, botao_miniapp(c, "Abrir Mango", "/telegram")
    if comando == "/split":
        botoes = botao_miniapp(c, "Nova divisão", "/telegram/split")
        return (
            "Abra o assistente para criar sua divisão."
            if botoes
            else "O assistente visual exige Mango self-hosted com miniapp HTTPS habilitado."
        ), botoes
    if comando == "/revisar" and user.tipo == "completo":
        return (
            rotina_diaria.relatorio(db, user, datetime.now(UTC)) or "Nenhuma transação pendente."
        ), botao_miniapp(c, "Revisar", "/telegram/revisao")
    if comando in {"/divisoes", "/resumo"} and (comando != "/resumo" or user.tipo == "completo"):
        token = emitir(db, user.id, "delegada", job.id)
        result = await servidor.call_tool(
            "saldos_divisao" if comando == "/divisoes" else "resumo_financeiro",
            {"formato": "lista"},
            ia_tools.ContextoInterno(autorizacao=f"Bearer {token}", mcp_server=servidor),
        )
        return "\n".join(p.text for p in result.content if p.type == "text"), (
            botao_miniapp(c, "Divisões", "/telegram/divisoes") if comando == "/divisoes" else None
        )
    if texto.startswith("/"):
        return "Comando indisponível. Use /ajuda.", None
    if user.tipo != "completo":
        return "Sua conta tem acesso às funções de divisão. Use /ajuda.", None
    token = emitir(db, user.id, "delegada", job.id)
    resposta = await ia.conversar(db, job, token)
    db.expire_all()
    op = db.scalar(
        select(OperacaoIntegracao).where(
            OperacaoIntegracao.trabalho_id == job.id,
            OperacaoIntegracao.tipo == "ia",
            OperacaoIntegracao.status == "preparando",
        )
    )
    if op:
        dados = json.loads(op.payload)
        if dados["confirmar"]:
            op.status = "pendente"
            db.commit()
            return resumir_proposta(dados), confirmacao(op.id)
        return await ia_tools.aplicar(servidor, db, user.id, op.id, token), None
    return resposta, None


def resumir_proposta(dados):
    nomes = {
        "atualizar_transacoes": "Editar transações",
        "vincular_objetivo": "Vincular objetivo",
        "criar_assinatura": "Criar assinatura",
        "atualizar_assinatura": "Editar assinatura",
        "rejeitar_candidato_assinatura": "Rejeitar sugestão de assinatura",
        "excluir_assinatura": "Excluir assinatura",
        "criar_divisao": "Criar divisão",
        "quitar_divisao": "Marcar divisão como paga",
        "reabrir_divisao": "Reabrir divisão",
        "excluir_divisao": "Excluir divisão",
    }
    campos = {
        "ids": "Transações",
        "revisada": "Revisada",
        "descricao": "Descrição",
        "observacoes": "Observações",
        "categoria": "Categoria",
        "assinatura_id": "Assinatura",
        "provento_id": "Provento",
        "valor_total_centavos": "Valor total (centavos)",
        "valor_centavos": "Valor (centavos)",
        "pago_por_usuario_id": "Pagador",
        "despesa_id": "Divisão",
        "nao_e_assinatura": "Não é assinatura",
        "eh_transferencia": "Transferência",
        "participantes": "Participantes",
    }
    linhas = ["Confira as alterações. A confirmação vale por dez minutos."]
    if dados.get("efeitos"):
        linhas.append(f"Transações afetadas, incluindo propagação: {dados['efeitos']}.")
    for chamada in dados["chamadas"]:
        linhas.append("\n" + nomes.get(chamada["nome"], "Alteração"))
        for campo, valor in chamada["args"].items():
            if isinstance(valor, bool):
                valor = "Sim" if valor else "Não"
            elif isinstance(valor, list):
                valor = ", ".join(map(str, valor))
            linhas.append(f"• {campos.get(campo, campo.replace('_', ' ').capitalize())}: {valor}")
    return "\n".join(linhas)


def confirmacao(op_id):
    return [
        [
            {"text": "Confirmar", "callback_data": "sim:" + op_id},
            {"text": "Cancelar", "callback_data": "nao:" + op_id},
        ]
    ]


def _worker():
    from app.services.telegram import instancia

    ultima_limpeza = 0.0
    while not _parar.is_set():
        job_id = None
        with _claim, SessionLocal() as db:
            ocupados = select(TrabalhoTelegram.usuario_id).where(
                TrabalhoTelegram.status == "executando"
            )
            job = db.scalar(
                select(TrabalhoTelegram)
                .where(
                    TrabalhoTelegram.status == "pendente",
                    TrabalhoTelegram.usuario_id.not_in(ocupados),
                )
                .order_by(TrabalhoTelegram.id)
                .limit(1)
            )
            # Retenção independe de novas conversas e da IA estar habilitada.
            if time.monotonic() - ultima_limpeza > 3600:
                db.execute(
                    delete(MensagemIa).where(
                        MensagemIa.criado_em < datetime.now(UTC) - timedelta(days=7)
                    )
                )
                db.commit()
                ultima_limpeza = time.monotonic()
            if job:
                job.status, job_id = "executando", job.id
                db.commit()
        if job_id is None:
            _parar.wait(1)
            continue
        with SessionLocal() as db:
            job = db.get(TrabalhoTelegram, job_id)
            try:
                geral = instancia(db)
                vinculo = db.scalar(
                    select(ConfigTelegram).where(ConfigTelegram.usuario_id == job.usuario_id)
                )
                user = db.get(Usuario, job.usuario_id)
                if (
                    not geral.telegram_ativo
                    or geral.telegram_bot_id != job.bot_id
                    or not vinculo
                    or not vinculo.ativo
                    or vinculo.chat_id != job.chat_id
                    or not user
                    or not user.ativo
                ):
                    job.status = "cancelado"
                    db.commit()
                    continue
                with TelegramClient(geral.telegram_token_cifrado) as cliente:
                    try:
                        texto, botoes = asyncio.run(executar(db, job, cliente))
                    except Exception as exc:
                        from mcp.server.mcpserver.exceptions import ToolError

                        from app.exceptions import DomainError

                        db.rollback()
                        texto = (
                            str(exc)
                            if isinstance(exc, (DomainError, ToolError))
                            else (
                                "Não foi possível concluir. "
                                "Tente uma solicitação menor ou verifique a conexão."
                            )
                        )
                        botoes = None
                        job.erro = "execucao_falhou"
                        db.execute(
                            update(OperacaoIntegracao)
                            .where(
                                OperacaoIntegracao.trabalho_id == job.id,
                                OperacaoIntegracao.status == "preparando",
                            )
                            .values(status="cancelada")
                        )
                        db.commit()
                    db.expire_all()
                    # Desvinculação pode ocorrer durante a chamada lenta ao provedor.
                    vinculo = db.scalar(
                        select(ConfigTelegram).where(ConfigTelegram.usuario_id == job.usuario_id)
                    )
                    if (
                        not instancia(db).telegram_ativo
                        or instancia(db).telegram_bot_id != job.bot_id
                        or not db.get(Usuario, job.usuario_id).ativo
                        or not vinculo
                        or not vinculo.ativo
                        or vinculo.chat_id != job.chat_id
                        or job.status != "executando"
                    ):
                        job.status = "cancelado"
                        db.commit()
                        continue
                    for i in range(0, len(texto), 3900):
                        cliente.send_message(
                            job.chat_id,
                            texto[i : i + 3900],
                            botoes=botoes if i + 3900 >= len(texto) else None,
                        )
                job.status = "concluido"
            except TelegramError as exc:
                job.status, job.erro = "incerto", exc.codigo
            except Exception:
                db.rollback()
                job.status, job.erro = "incerto", "execucao_interrompida"
                logger.error("trabalho Telegram interrompido")
            finally:
                revogar(db, trabalho_id=job_id)
                job.evento = None
                db.commit()


def iniciar():
    _threads[:] = [thread for thread in _threads if thread.is_alive()]
    if _threads:
        return
    with SessionLocal() as db:
        db.execute(
            update(TrabalhoTelegram)
            .where(TrabalhoTelegram.status == "executando")
            .values(status="incerto", evento=None)
        )
        db.execute(
            update(OperacaoIntegracao)
            .where(OperacaoIntegracao.status == "preparando")
            .values(status="cancelada")
        )
        db.commit()
        revogar(db)
    _parar.clear()
    for i in range(2):
        thread = threading.Thread(target=_worker, name=f"mango-conversa-{i}", daemon=True)
        _threads.append(thread)
        thread.start()


def parar():
    _parar.set()
    for thread in _threads:
        thread.join(timeout=1)
    _threads[:] = [thread for thread in _threads if thread.is_alive()]
    with SessionLocal() as db:
        revogar(db)
