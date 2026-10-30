"""Prévia por simulação das regras reais e aplicação transacional com recibo idempotente."""

import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.db.atomic import atomica
from app.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.assinatura import Assinatura
from app.models.categoria import RegraCategorizacao
from app.models.integracao import OperacaoIntegracao
from app.models.transacao import Transacao
from app.repositories.transacao import TransacaoRepository
from app.schemas.revisao import RevisaoPreparar
from app.security.current_user import _aware


def serializar(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str)


def estado(db: Session, usuario_id: int) -> dict:
    resultado = {}
    for model in (Transacao, Assinatura, RegraCategorizacao):
        rows = db.scalars(
            select(model).where(model.usuario_id == usuario_id).order_by(model.id).with_for_update()
        ).all()
        resultado[model.__tablename__] = {
            str(row.id): {c.key: getattr(row, c.key) for c in inspect(model).columns}
            for row in rows
        }
    return resultado


def versao(obj) -> str:
    return hashlib.sha256(serializar(obj).encode()).hexdigest()


def versao_transacao(obj: Transacao) -> str:
    return versao({c.key: getattr(obj, c.key) for c in inspect(Transacao).columns})


def executar_revisao(db: Session, usuario_id: int, payload: RevisaoPreparar):
    from app.repositories.assinatura import AssinaturaRepository
    from app.repositories.categoria import CategoriaRepository
    from app.repositories.conta import ContaRepository
    from app.routers.transacao import atualizar
    from app.schemas.transacao import TransacaoUpdate
    from app.services import regra_categorizacao

    repo = TransacaoRepository(db, usuario_id)
    transacao = repo.get(payload.transacao_id)
    if transacao is None:
        raise NotFoundError("transação não encontrada")
    if versao_transacao(transacao) != payload.versao:
        raise ConflictError("a transação mudou; recarregue antes de salvar")
    dados = payload.alteracoes.model_dump(exclude_unset=True)
    if payload.assinatura:
        novo = payload.assinatura.model_dump()
        if (
            novo.get("categoria_id")
            and CategoriaRepository(db, usuario_id).get(novo["categoria_id"]) is None
        ):
            raise ValidationError("categoria não encontrada")
        if novo.get("conta_id") and ContaRepository(db, usuario_id).get(novo["conta_id"]) is None:
            raise ValidationError("conta não encontrada")
        assinatura = AssinaturaRepository(db, usuario_id).create(**novo)
        dados["assinatura_id"] = assinatura.id
        dados.pop("categoria_override_id", None)
        dados.pop("categoria_ajustada_usuario", None)
    if payload.regra:
        regra_categorizacao.criar(db, usuario_id, **payload.regra.model_dump())
    dados["revisada"] = True
    return atualizar(payload.transacao_id, TransacaoUpdate(**dados), repo).model_dump(mode="json")


def preparar_revisao(db: Session, usuario_id: int, payload: RevisaoPreparar):
    antes = estado(db, usuario_id)
    anterior = db.info.get("operacao_atomica", False)
    db.info["operacao_atomica"] = True
    try:
        with db.begin_nested() as savepoint:
            executar_revisao(db, usuario_id, payload)
            db.flush()
            depois = estado(db, usuario_id)
            alterados = [
                key
                for key, row in depois[Transacao.__tablename__].items()
                if serializar(row) != serializar(antes[Transacao.__tablename__].get(key))
            ]
            savepoint.rollback()
    finally:
        db.info["operacao_atomica"] = anterior
    op = OperacaoIntegracao(
        id=secrets.token_urlsafe(24),
        usuario_id=usuario_id,
        tipo="revisao",
        payload=serializar(
            {"versao": versao(antes), "dados": payload.model_dump(mode="json", exclude_unset=True)}
        ),
        expira_em=datetime.now(UTC) + timedelta(minutes=10),
    )
    db.add(op)
    db.commit()
    efeitos = []
    if len(alterados) > 1:
        efeitos.append(
            f"Esta revisão altera {len(alterados)} transações, incluindo parcelas ou regras."
        )
    if payload.regra:
        efeitos.append("A nova regra também será usada nas próximas importações.")
    if payload.assinatura:
        efeitos.append("Uma assinatura será criada e vinculada à transação.")
    return {
        "operacao_id": op.id,
        "transacoes_afetadas": len(alterados),
        "exige_confirmacao": len(alterados) > 1 or bool(payload.regra),
        "efeitos": efeitos,
    }


def aplicar_revisao(db: Session, usuario_id: int, operacao_id: str):
    with atomica(db):
        op = db.scalar(
            select(OperacaoIntegracao)
            .where(
                OperacaoIntegracao.id == operacao_id, OperacaoIntegracao.usuario_id == usuario_id
            )
            .with_for_update()
        )
        if not op or op.tipo != "revisao":
            raise NotFoundError("operação não encontrada")
        if op.status == "concluida":
            return json.loads(op.resultado)
        if op.status != "pendente" or _aware(op.expira_em) <= datetime.now(UTC):
            raise ConflictError("operação expirada ou cancelada")
        dados = json.loads(op.payload)
        if versao(estado(db, usuario_id)) != dados["versao"]:
            raise ConflictError("os dados mudaram; prepare a revisão novamente")
        resultado = executar_revisao(db, usuario_id, RevisaoPreparar.model_validate(dados["dados"]))
        resultado["versao"] = versao_transacao(
            TransacaoRepository(db, usuario_id).get(dados["dados"]["transacao_id"])
        )
        op.status, op.resultado = "concluida", serializar(resultado)
    return resultado


def criar_divisao_idempotente(db, usuario_id, payload, chave):
    from sqlalchemy.exc import IntegrityError

    from app.services import divisao

    identificador = versao(["divisao", usuario_id, chave])
    conteudo = serializar(payload.model_dump(mode="json"))

    def recibo():
        op = db.get(OperacaoIntegracao, identificador)
        if op:
            if op.payload != conteudo:
                raise ConflictError("chave já usada com outra divisão")
            return json.loads(op.resultado)
        return None

    anterior = recibo()
    if anterior is not None:
        return anterior
    try:
        with atomica(db):
            op = OperacaoIntegracao(
                id=identificador,
                usuario_id=usuario_id,
                tipo="divisao",
                payload=conteudo,
                status="preparando",
                expira_em=datetime.now(UTC) + timedelta(days=7),
            )
            db.add(op)
            db.flush()
            resultado = divisao.criar(db, usuario_id, payload).model_dump(mode="json")
            op.status, op.resultado = "concluida", serializar(resultado)
        return resultado
    except IntegrityError:
        db.rollback()
        anterior = recibo()
        if anterior is not None:
            return anterior
        raise
