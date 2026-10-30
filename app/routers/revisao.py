from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.usuario import Usuario
from app.repositories.transacao import TransacaoRepository
from app.routers.transacao import _read
from app.schemas.revisao import (
    OperacaoAplicar,
    RevisaoFila,
    RevisaoItem,
    RevisaoPreparar,
    RevisaoPrevia,
)
from app.security.current_user import exigir_usuario_completo
from app.services import operacoes
from app.services.categoria_resolucao import carregar_contexto
from app.services.periodo import hoje_sp, limites_sp
from app.services.revisao import corte_revisao

router = APIRouter(prefix="/revisao", tags=["revisao"])


@router.get("", response_model=RevisaoFila)
def fila(
    cursor: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    user: Usuario = Depends(exigir_usuario_completo),
):
    # Keyset por id evita saltos quando o cliente remove itens da fila ao salvar.
    repo = TransacaoRepository(db, user.id)
    itens, total = repo.listar_filtrado(
        pendente_revisao=True,
        corte_revisao=corte_revisao(user.revisao_desde),
        fim=limites_sp(hoje_sp(), hoje_sp())[1],
        ocultar_pagamento_fatura=True,
        limit=51,
        antes_id=cursor,
        order="id",
    )
    ctx = carregar_contexto(db, user.id)
    return {
        "items": [
            {**_read(t, ctx).model_dump(mode="json"), "versao": operacoes.versao_transacao(t)}
            for t in itens[:50]
        ],
        "total": total,
        "cursor": itens[49].id if len(itens) > 50 else None,
    }


@router.post("/preparar", response_model=RevisaoPrevia)
def preparar(
    payload: RevisaoPreparar,
    db: Session = Depends(get_db),
    user: Usuario = Depends(exigir_usuario_completo),
):
    return operacoes.preparar_revisao(db, user.id, payload)


@router.post("/aplicar", response_model=RevisaoItem)
def aplicar(
    payload: OperacaoAplicar,
    db: Session = Depends(get_db),
    user: Usuario = Depends(exigir_usuario_completo),
):
    return operacoes.aplicar_revisao(db, user.id, payload.operacao_id)


@router.get("/{transacao_id}", response_model=RevisaoItem)
def item(
    transacao_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(exigir_usuario_completo),
):
    from app.exceptions import NotFoundError

    t = TransacaoRepository(db, user.id).get(transacao_id)
    if t is None:
        raise NotFoundError("transação não encontrada")
    return {
        **_read(t, carregar_contexto(db, user.id)).model_dump(mode="json"),
        "versao": operacoes.versao_transacao(t),
    }
