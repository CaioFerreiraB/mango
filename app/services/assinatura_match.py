"""Auto-vínculo transação → assinatura por nome exato (§4.7). Roda após o sync.

Cada assinatura tem `nomes_transacao` (aliases). Uma transação ainda sem assinatura cujo nome
(`merchant_nome` senão `description`, normalizado) case exatamente um alias é vinculada. Só preenche
quando `assinatura_id` é NULL → idempotente e nunca sobrescreve um vínculo manual (que também
sobrevive ao re-sync via `CAMPOS_USUARIO`).
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.assinatura import Assinatura
from app.models.transacao import Transacao
from app.repositories.transacao import TransacaoRepository
from app.services.assinatura_deteccao import normalizar_nome


def aplicar_match_assinaturas(db: Session, usuario_id: int, *, desde: date | None = None) -> None:
    aliases = _mapa_aliases(db, usuario_id)
    if not aliases:
        return
    repo = TransacaoRepository(db, usuario_id)
    for t in _transacoes_sem_assinatura(db, usuario_id, desde):
        chave = normalizar_nome(t.merchant_nome or t.description)
        assinatura_id = aliases.get(chave)
        if assinatura_id is not None:
            repo.update(t, assinatura_id=assinatura_id)


def revincular_assinatura(db: Session, usuario_id: int, assinatura: Assinatura) -> int:
    """Re-varre TODAS as transações do usuário após editar os aliases (`nomes_transacao`) de UMA
    assinatura: toda transação cujo nome normalizado casa um alias passa a apontar para ela (§4.7).

    Diferente do match do sync, aqui o vínculo é override — corrige um vínculo antigo/errado
    ("colocando a assinatura correta"), então não exige `assinatura_id` NULL. Devolve quantas foram
    (re)vinculadas. ponytail: só adiciona vínculo, nunca desvincula uma transação cujo nome deixou
    de casar (removeria dado com base num diff de aliases que não guardamos); desvincular é manual.
    """
    alvos = {c for n in assinatura.nomes_transacao if (c := normalizar_nome(n))}
    if not alvos:
        return 0
    repo = TransacaoRepository(db, usuario_id)
    total = 0
    for t in repo.list():
        if t.assinatura_id == assinatura.id:
            continue
        if normalizar_nome(t.merchant_nome or t.description) in alvos:
            repo.update(t, assinatura_id=assinatura.id)
            total += 1
    return total


def _mapa_aliases(db: Session, usuario_id: int) -> dict[str, int]:
    """`{alias normalizado: assinatura_id}` das assinaturas ativas. Alias vazio é ignorado; em
    conflito, a última assinatura vence (raro em escala pessoal)."""
    mapa: dict[str, int] = {}
    stmt = select(Assinatura).where(Assinatura.usuario_id == usuario_id, Assinatura.ativa.is_(True))
    for a in db.scalars(stmt).all():
        for alias in a.nomes_transacao:
            chave = normalizar_nome(alias)
            if chave:
                mapa[chave] = a.id
    return mapa


def _transacoes_sem_assinatura(db: Session, usuario_id: int, desde: date | None) -> list[Transacao]:
    stmt = select(Transacao).where(
        Transacao.usuario_id == usuario_id, Transacao.assinatura_id.is_(None)
    )
    if desde is not None:
        stmt = stmt.where(Transacao.date >= datetime(desde.year, desde.month, desde.day))
    return list(db.scalars(stmt).all())
