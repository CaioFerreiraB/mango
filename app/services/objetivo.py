"""Objetivos (§4.8, decisão #4): valor guardado e progresso calculados em runtime.

Valor guardado = soma dos saldos de contas + investimentos vinculados pela FK `objetivo_id`.
A regra 1:1-max (#4) já é garantida pela FK escalar em conta/investimento; aqui só somamos.
Tudo escopado por `usuario_id` (§5.2).
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.ativo import Ativo
from app.models.conta import Conta
from app.models.investimento import Investimento
from app.models.objetivo import Objetivo
from app.schemas.objetivo import ObjetivoDetalheRead, ObjetivoRead, ObjetivoVinculo

_VINCULAVEIS = (Conta, Investimento)


def _progresso(guardado: int, alvo: int) -> float:
    return round(min(guardado / alvo, 1.0), 4) if alvo else 0.0


def valores_guardados(db: Session, usuario_id: int) -> dict[int, int]:
    """{objetivo_id: soma de saldos vinculados} para todos os objetivos do usuário."""
    guardado: dict[int, int] = {}
    for tabela in _VINCULAVEIS:
        rows = db.execute(
            select(tabela.objetivo_id, func.coalesce(func.sum(tabela.saldo_centavos), 0))
            .where(tabela.usuario_id == usuario_id, tabela.objetivo_id.is_not(None))
            .group_by(tabela.objetivo_id)
        ).all()
        for objetivo_id, total in rows:
            # int(): no Postgres SUM(BIGINT) volta NUMERIC → Decimal, que a API serializava como
            # string ("500000") porque o atributo é atribuído sem validação em `_enriquecer`.
            guardado[objetivo_id] = guardado.get(objetivo_id, 0) + int(total)
    return guardado


def _enriquecer(obj: Objetivo, guardado: int) -> ObjetivoRead:
    read = ObjetivoRead.model_validate(obj)
    read.valor_guardado_centavos = guardado
    read.progresso = _progresso(guardado, obj.valor_alvo_centavos)
    return read


def enriquecer_um(db: Session, usuario_id: int, obj: Objetivo) -> ObjetivoRead:
    guardado = valores_guardados(db, usuario_id).get(obj.id, 0)
    return _enriquecer(obj, guardado)


def listar(db: Session, usuario_id: int) -> list[ObjetivoRead]:
    guardados = valores_guardados(db, usuario_id)
    objetivos = db.scalars(
        select(Objetivo).where(Objetivo.usuario_id == usuario_id).order_by(Objetivo.id)
    ).all()
    return [_enriquecer(o, guardados.get(o.id, 0)) for o in objetivos]


def _vinculos(db: Session, usuario_id: int, objetivo_id: int) -> list[ObjetivoVinculo]:
    contas = db.scalars(
        select(Conta).where(Conta.usuario_id == usuario_id, Conta.objetivo_id == objetivo_id)
    ).all()
    vinculos = [
        ObjetivoVinculo(tipo="conta", id=c.id, nome=c.nome, saldo_centavos=c.saldo_centavos)
        for c in contas
    ]
    # Investimento inteiro: as compras de um ativo viram uma linha só (nome do ativo, saldo somado).
    # `id` = compra de maior saldo — representante p/ ícone e desvincular (que age no ativo todo).
    rows = db.execute(
        select(Investimento, Ativo.nome)
        .outerjoin(Ativo, Ativo.id == Investimento.ativo_id)
        .where(Investimento.usuario_id == usuario_id, Investimento.objetivo_id == objetivo_id)
        .order_by(Investimento.saldo_centavos.desc(), Investimento.id)
    ).all()
    grupos: dict[tuple[str, int], ObjetivoVinculo] = {}
    for inv, nome_ativo in rows:
        chave = ("ativo", inv.ativo_id) if inv.ativo_id is not None else ("inv", inv.id)
        if (v := grupos.get(chave)) is None:
            grupos[chave] = ObjetivoVinculo(
                tipo="investimento",
                id=inv.id,
                nome=nome_ativo or inv.nome,
                saldo_centavos=inv.saldo_centavos,
            )
        else:
            v.saldo_centavos += inv.saldo_centavos
    return vinculos + list(grupos.values())


def obter(db: Session, usuario_id: int, objetivo_id: int) -> ObjetivoDetalheRead | None:
    obj = db.scalars(
        select(Objetivo).where(Objetivo.usuario_id == usuario_id, Objetivo.id == objetivo_id)
    ).first()
    if obj is None:
        return None
    vinculos = _vinculos(db, usuario_id, objetivo_id)
    guardado = sum(v.saldo_centavos for v in vinculos)
    detalhe = ObjetivoDetalheRead.model_validate(obj)
    detalhe.valor_guardado_centavos = guardado
    detalhe.progresso = _progresso(guardado, obj.valor_alvo_centavos)
    detalhe.vinculos = vinculos
    return detalhe
