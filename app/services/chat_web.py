"""Chat no app: execução numa thread própria; a resposta é salva mesmo se o browser sair.

A rota valida, reserva a cota e emite a credencial `web` dentro do request (erros viram HTTP
imediato); a thread conversa com o provedor e publica eventos numa fila que a rota repassa
como SSE.

`ponytail:` execuções em memória por processo (mesma premissa do `sync_manual`: 1 worker);
multi-worker exigiria levar o estado "executando" para o banco.
"""

import asyncio
import json
import logging
import queue
import threading
from datetime import UTC, datetime, timedelta

from mcp.server.mcpserver.exceptions import ToolError
from sqlalchemy import delete, exists, select, update

from app.db.session import SessionLocal
from app.exceptions import ConflictError, DomainError, NotFoundError, ValidationError
from app.models.integracao import (
    ConversaIa,
    CredencialIntegracao,
    MensagemIa,
    OperacaoIntegracao,
)
from app.security.current_user import _aware
from app.services import ia, ia_tools
from app.services.integracao_auth import configuracao, emitir, revogar

logger = logging.getLogger("app.ia.chat")

RETENCAO = timedelta(days=7)
HISTORICO = 40  # 20 interações; a mensagem atual vai além disso
TITULO = 60
ERRO_GENERICO = "Não foi possível concluir. Tente uma solicitação menor."

_lock = threading.Lock()
_execucoes: dict[int, dict] = {}  # usuario_id → {"conversa_id", "parar": Event}


def executando(usuario_id: int, conversa_id: int | None = None) -> bool:
    with _lock:
        atual = _execucoes.get(usuario_id)
    return bool(atual and (conversa_id is None or atual["conversa_id"] == conversa_id))


def limpar(db) -> None:
    """Retenção lazy: mensagens >7 dias, conversas vazias, credenciais web vencidas há dias."""
    limite = datetime.now(UTC) - RETENCAO
    db.execute(delete(MensagemIa).where(MensagemIa.criado_em < limite))
    db.execute(
        delete(ConversaIa).where(
            ConversaIa.atualizado_em < limite,
            ~exists().where(MensagemIa.conversa_id == ConversaIa.id),
        )
    )
    db.execute(
        delete(CredencialIntegracao).where(
            CredencialIntegracao.tipo == "web",
            CredencialIntegracao.expira_em < datetime.now(UTC) - timedelta(days=2),
        )
    )
    db.commit()


def conversa_do_usuario(db, usuario_id: int, conversa_id: int) -> ConversaIa:
    conversa = db.scalar(
        select(ConversaIa).where(ConversaIa.id == conversa_id, ConversaIa.usuario_id == usuario_id)
    )
    if conversa is None:
        raise NotFoundError("conversa não encontrada")
    return conversa


def proposta_pendente(db, usuario_id: int, conversa_id: int) -> OperacaoIntegracao | None:
    return db.scalar(
        select(OperacaoIntegracao)
        .join(MensagemIa, MensagemIa.id == OperacaoIntegracao.mensagem_id)
        .where(
            OperacaoIntegracao.usuario_id == usuario_id,
            OperacaoIntegracao.tipo == "ia",
            OperacaoIntegracao.status == "pendente",
            OperacaoIntegracao.expira_em > datetime.now(UTC),
            MensagemIa.conversa_id == conversa_id,
        )
        .order_by(OperacaoIntegracao.criado_em.desc())
        .limit(1)
    )


def iniciar(
    db, usuario_id: int, conversa_id: int | None, texto: str | None, regenerar: bool
) -> tuple[ConversaIa, queue.Queue]:
    if not ia.disponivel(db, usuario_id):
        raise ConflictError("Ative a conversa em Configurações → Inteligência artificial.")
    limpar(db)
    with _lock:
        if usuario_id in _execucoes:
            raise ConflictError("já existe uma resposta em andamento")
        parar = threading.Event()
        _execucoes[usuario_id] = {"conversa_id": None, "parar": parar}
    try:
        conversa, pedido, token, mensagens = _preparar(
            db, usuario_id, conversa_id, texto, regenerar
        )
    except BaseException:
        with _lock:
            _execucoes.pop(usuario_id, None)
        raise
    with _lock:
        _execucoes[usuario_id]["conversa_id"] = conversa.id
    fila: queue.Queue = queue.Queue()
    config = ia.congelar(configuracao(db))
    threading.Thread(
        target=_rodar,
        args=(usuario_id, conversa.id, pedido.id, token, mensagens, config, fila, parar),
        daemon=True,
        name="chat-web",
    ).start()
    return conversa, fila


def _preparar(db, usuario_id, conversa_id, texto, regenerar):
    if conversa_id is None:
        if regenerar or not texto:
            raise ValidationError("informe a mensagem")
        conversa = ConversaIa(usuario_id=usuario_id, titulo=" ".join(texto.split())[:TITULO])
        db.add(conversa)
        db.flush()
    else:
        conversa = conversa_do_usuario(db, usuario_id, conversa_id)
    if regenerar:
        pedido = _reabrir_ultimo_pedido(db, usuario_id, conversa.id)
    else:
        pedido = MensagemIa(
            usuario_id=usuario_id, conversa_id=conversa.id, papel="user", conteudo=texto
        )
        db.add(pedido)
        db.flush()
    conversa.atualizado_em = datetime.now(UTC)
    # Reserva e credencial no mesmo commit da mensagem: sem cota, nada é gravado.
    token = ia.reservar_cota(
        db, usuario_id, lambda: emitir(db, usuario_id, "web", mensagem_id=pedido.id)
    )
    return conversa, pedido, token, _historico(db, usuario_id, conversa.id, pedido.id)


def _reabrir_ultimo_pedido(db, usuario_id, conversa_id) -> MensagemIa:
    """Regenerar: o último pedido volta a ser a execução; respostas e propostas dele somem."""
    pedido = db.scalar(
        select(MensagemIa)
        .where(
            MensagemIa.usuario_id == usuario_id,
            MensagemIa.conversa_id == conversa_id,
            MensagemIa.papel == "user",
        )
        .order_by(MensagemIa.id.desc())
        .limit(1)
    )
    if pedido is None:
        raise ValidationError("nada para regenerar")
    cancelar_propostas(db, usuario_id, pedido.id)
    db.execute(
        delete(MensagemIa).where(
            MensagemIa.usuario_id == usuario_id,
            MensagemIa.conversa_id == conversa_id,
            MensagemIa.id > pedido.id,
        )
    )
    return pedido


def _historico(db, usuario_id, conversa_id, pedido_id) -> list[dict]:
    """Instruções + últimas interações da conversa até o pedido atual (WHIST01)."""
    anteriores = db.scalars(
        select(MensagemIa)
        .where(
            MensagemIa.usuario_id == usuario_id,
            MensagemIa.conversa_id == conversa_id,
            MensagemIa.id <= pedido_id,
        )
        .order_by(MensagemIa.id.desc())
        .limit(HISTORICO + 1)
    ).all()
    mensagens = [ia.instrucoes("web")]
    mensagens += [{"role": m.papel, "content": m.conteudo} for m in reversed(anteriores)]
    return mensagens


def cancelar_propostas(db, usuario_id: int, mensagem_id: int | None = None) -> None:
    stmt = update(OperacaoIntegracao).where(
        OperacaoIntegracao.usuario_id == usuario_id,
        OperacaoIntegracao.tipo == "ia",
        OperacaoIntegracao.mensagem_id.is_not(None),
        OperacaoIntegracao.status.in_(["preparando", "pendente"]),
    )
    if mensagem_id is not None:
        stmt = stmt.where(OperacaoIntegracao.mensagem_id == mensagem_id)
    db.execute(stmt.values(status="cancelada"))


def parar(db, usuario_id: int) -> None:
    with _lock:
        atual = _execucoes.get(usuario_id)
    if atual:
        atual["parar"].set()
    revogar(db, usuario_id=usuario_id, tipos=("web",))
    db.expire_all()
    db.execute(
        update(OperacaoIntegracao)
        .where(
            OperacaoIntegracao.usuario_id == usuario_id,
            OperacaoIntegracao.mensagem_id.is_not(None),
            OperacaoIntegracao.status == "preparando",
        )
        .values(status="cancelada")
    )
    db.commit()


async def _ate_parar(coro, parar: threading.Event):
    tarefa = asyncio.ensure_future(coro)
    while not tarefa.done():
        await asyncio.wait({tarefa}, timeout=0.3)
        if parar.is_set() and not tarefa.done():
            tarefa.cancel()
    return await tarefa


def _salvar(db, usuario_id, conversa_id, texto) -> int:
    resposta = MensagemIa(
        usuario_id=usuario_id, conversa_id=conversa_id, papel="assistant", conteudo=texto
    )
    db.add(resposta)
    db.commit()
    return resposta.id


def _concluir(db, usuario_id, conversa_id, pedido_id, token, evento) -> None:
    """Escritas preparadas na execução: proposta para o clique, ou aplicação direta (IA01)."""
    from app.mcp.servidor import servidor

    db.expire_all()
    op = db.scalar(
        select(OperacaoIntegracao).where(
            OperacaoIntegracao.usuario_id == usuario_id,
            OperacaoIntegracao.mensagem_id == pedido_id,
            OperacaoIntegracao.tipo == "ia",
            OperacaoIntegracao.status == "preparando",
        )
    )
    if op is None:
        return
    if json.loads(op.payload)["confirmar"]:
        op.status = "pendente"
        db.commit()
        evento("proposta", serializar_proposta(op))
        return
    resultado = asyncio.run(ia_tools.aplicar(servidor, db, usuario_id, op.id, token))
    _salvar(db, usuario_id, conversa_id, resultado)
    evento("aplicada", {"resultado": resultado})


def _rodar(usuario_id, conversa_id, pedido_id, token, mensagens, config, fila, parar_evt):
    partes: list[str] = []

    def evento(tipo, dados):
        if tipo == "delta":
            partes.append(dados["texto"])
        fila.put((tipo, dados))

    with SessionLocal() as db:
        try:
            evento("status", {"texto": "Pensando…"})
            resposta = ia.responder(config, mensagens, token, evento, transmitir=True)
            try:
                texto = asyncio.run(_ate_parar(resposta, parar_evt))
            except asyncio.CancelledError:
                # Parado pelo usuário: o que já chegou fica salvo; escritas são descartadas.
                db.rollback()
                cancelar_propostas(db, usuario_id, pedido_id)
                db.commit()
                parcial = "".join(partes).strip()
                salvo = _salvar(db, usuario_id, conversa_id, parcial) if parcial else None
                evento("fim", {"mensagem_id": salvo})
                return
            mensagem_id = _salvar(db, usuario_id, conversa_id, texto)
            _concluir(db, usuario_id, conversa_id, pedido_id, token, evento)
            evento("fim", {"mensagem_id": mensagem_id})
        except Exception as exc:
            db.rollback()
            cancelar_propostas(db, usuario_id, pedido_id)
            db.commit()
            conhecido = isinstance(exc, (DomainError, ToolError))
            if not conhecido:
                logger.exception("execução do chat falhou")
            evento("erro", {"mensagem": str(exc) if conhecido else ERRO_GENERICO})
        finally:
            revogar(db, usuario_id=usuario_id, tipos=("web",))
            with _lock:
                _execucoes.pop(usuario_id, None)
            fila.put(None)


def serializar_proposta(op: OperacaoIntegracao) -> dict:
    return {
        "operacao_id": op.id,
        "resumo": ia_tools.resumir_proposta(json.loads(op.payload)),
        "expira_em": _aware(op.expira_em).isoformat(),
    }


async def confirmar(db, usuario_id: int, op_id: str) -> str:
    """Aplica a proposta do chat web (clique humano) e registra o resultado na conversa."""
    from app.mcp.servidor import servidor

    op = db.scalar(
        select(OperacaoIntegracao).where(
            OperacaoIntegracao.id == op_id,
            OperacaoIntegracao.usuario_id == usuario_id,
            OperacaoIntegracao.mensagem_id.is_not(None),
        )
    )
    if op is None or op.status != "pendente":
        raise NotFoundError("proposta indisponível ou já utilizada")
    pedido = db.scalar(
        select(MensagemIa).where(
            MensagemIa.id == op.mensagem_id, MensagemIa.usuario_id == usuario_id
        )
    )
    if pedido is None:
        raise NotFoundError("proposta indisponível ou já utilizada")
    # A aplicação passa pelas mesmas tools; uma credencial curta, revogada ao fim.
    token = emitir(db, usuario_id, "web_confirma", mensagem_id=op.mensagem_id)
    try:
        resultado = await ia_tools.aplicar(servidor, db, usuario_id, op_id, token)
    except ToolError as exc:
        db.rollback()
        raise ConflictError(str(exc)) from None
    finally:
        revogar(db, usuario_id=usuario_id, tipos=("web_confirma",))
    db.add(
        MensagemIa(
            usuario_id=usuario_id,
            conversa_id=pedido.conversa_id,
            papel="assistant",
            conteudo=resultado,
        )
    )
    db.commit()
    return resultado


def cancelar(db, usuario_id: int, op_id: str) -> None:
    op = db.scalar(
        select(OperacaoIntegracao).where(
            OperacaoIntegracao.id == op_id,
            OperacaoIntegracao.usuario_id == usuario_id,
            OperacaoIntegracao.mensagem_id.is_not(None),
        )
    )
    if op is None or op.status != "pendente":
        raise NotFoundError("proposta indisponível ou já utilizada")
    op.status = "cancelada"
    db.commit()
