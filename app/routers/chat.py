"""Chat web com a IA (docs/dev/chat-web.md). Sob `/api/ia/…`: o 422 não ecoa o texto enviado."""

import asyncio
import json
import queue

from fastapi import APIRouter, Depends, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.exceptions import ConflictError
from app.models.integracao import ConversaIa, MensagemIa
from app.models.usuario import Usuario
from app.schemas.integracao import (
    ConversaIaRead,
    ConversaIaResumo,
    ConversaIaUpdate,
    MensagemIaCreate,
    ResultadoProposta,
)
from app.security.current_user import exigir_usuario_completo
from app.services import chat_web

router = APIRouter(tags=["chat"])
PING = 15  # s; mantém o proxy reverso sem timeout enquanto o provedor pensa


@router.get("/ia/conversas", response_model=list[ConversaIaResumo])
def listar(db: Session = Depends(get_db), user: Usuario = Depends(exigir_usuario_completo)):
    chat_web.limpar(db)
    return db.scalars(
        select(ConversaIa)
        .where(ConversaIa.usuario_id == user.id)
        .order_by(ConversaIa.atualizado_em.desc(), ConversaIa.id.desc())
    ).all()


@router.get("/ia/conversas/{conversa_id}", response_model=ConversaIaRead)
def obter(
    conversa_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(exigir_usuario_completo),
):
    conversa = chat_web.conversa_do_usuario(db, user.id, conversa_id)
    op = chat_web.proposta_pendente(db, user.id, conversa.id)
    return ConversaIaRead(
        id=conversa.id,
        titulo=conversa.titulo,
        atualizado_em=conversa.atualizado_em,
        mensagens=db.scalars(
            select(MensagemIa)
            .where(MensagemIa.usuario_id == user.id, MensagemIa.conversa_id == conversa.id)
            .order_by(MensagemIa.id)
        ).all(),
        proposta=chat_web.serializar_proposta(op) if op else None,
        executando=chat_web.executando(user.id, conversa.id),
    )


@router.patch("/ia/conversas/{conversa_id}", response_model=ConversaIaResumo)
def renomear(
    conversa_id: int,
    payload: ConversaIaUpdate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(exigir_usuario_completo),
):
    conversa = chat_web.conversa_do_usuario(db, user.id, conversa_id)
    conversa.titulo = payload.titulo.strip() or conversa.titulo
    db.commit()
    return conversa


@router.delete("/ia/conversas/{conversa_id}", status_code=204)
def excluir(
    conversa_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(exigir_usuario_completo),
):
    conversa = chat_web.conversa_do_usuario(db, user.id, conversa_id)
    if chat_web.executando(user.id, conversa.id):
        raise ConflictError("pare a resposta em andamento antes de excluir")
    for pedido_id in db.scalars(
        select(MensagemIa.id).where(
            MensagemIa.usuario_id == user.id, MensagemIa.conversa_id == conversa.id
        )
    ).all():
        chat_web.cancelar_propostas(db, user.id, pedido_id)
    db.delete(conversa)
    db.commit()
    return Response(status_code=204)


def _sse(tipo: str, dados: dict) -> str:
    return f"event: {tipo}\ndata: {json.dumps(dados, ensure_ascii=False)}\n\n"


@router.post(
    "/ia/mensagens",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}},
)
def enviar(
    payload: MensagemIaCreate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(exigir_usuario_completo),
):
    conversa, pedido_id, fila = chat_web.iniciar(
        db, user.id, payload.conversa_id, payload.texto, payload.regenerar, payload.chave
    )
    # `pedido_id` = o pedido já está gravado: o cliente reconcilia por id, não por texto.
    inicio = {"id": conversa.id, "titulo": conversa.titulo, "pedido_id": pedido_id}

    async def eventos():
        yield _sse("conversa", inicio)
        while True:
            try:
                item = await asyncio.to_thread(fila.get, True, PING)
            except queue.Empty:
                yield ": ping\n\n"
                continue
            if item is None:
                return
            yield _sse(*item)

    return StreamingResponse(
        eventos(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/ia/execucao/parar", status_code=204)
def parar(db: Session = Depends(get_db), user: Usuario = Depends(exigir_usuario_completo)):
    chat_web.parar(db, user.id)
    return Response(status_code=204)


@router.post("/ia/operacoes/{operacao_id}/confirmar", response_model=ResultadoProposta)
async def confirmar(
    operacao_id: str,
    db: Session = Depends(get_db),
    user: Usuario = Depends(exigir_usuario_completo),
):
    return ResultadoProposta(resultado=await chat_web.confirmar(db, user.id, operacao_id))


@router.post("/ia/operacoes/{operacao_id}/cancelar", status_code=204)
def cancelar(
    operacao_id: str,
    db: Session = Depends(get_db),
    user: Usuario = Depends(exigir_usuario_completo),
):
    chat_web.cancelar(db, user.id, operacao_id)
    return Response(status_code=204)
