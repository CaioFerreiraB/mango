"""Agrupa posições de renda fixa num `ativo` (§4.9, decisão do usuário). Roda após o sync,
junto do match de assinaturas.

Idempotente: só preenche `ativo_id` NULL — nunca desfaz um agrupamento manual (que sobrevive ao
re-sync via pop no upsert). Chave = ISIN (mais preciso) senão nome normalizado, então "Tesouro
Selic 2028" junta suas N compras já no 1º sync. Dois papéis distintos com a mesma chave juntam por
engano → o split é manual (ponytail: sem forma automática de distinguir CDBs de nome igual).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.investimento import Investimento
from app.repositories.ativo import AtivoRepository
from app.services.assinatura_deteccao import normalizar_nome

RENDA_FIXA = ("FIXED_INCOME",)


def _chave(inv: Investimento) -> str | None:
    if inv.isin:
        return f"isin:{inv.isin}"
    nome = normalizar_nome(inv.nome)
    return f"nome:{nome}" if nome else None


def agrupar_renda_fixa(db: Session, usuario_id: int) -> None:
    posicoes = db.scalars(
        select(Investimento).where(
            Investimento.usuario_id == usuario_id, Investimento.type.in_(RENDA_FIXA)
        )
    ).all()
    # Mapa das posições já agrupadas (chave → ativo_id) — semeia o agrupamento das novas.
    mapa: dict[str, int] = {
        chave: inv.ativo_id
        for inv in posicoes
        if inv.ativo_id is not None and (chave := _chave(inv)) is not None
    }
    repo = AtivoRepository(db, usuario_id)
    for inv in sorted((p for p in posicoes if p.ativo_id is None), key=lambda p: p.id):
        chave = _chave(inv)
        if chave is None:
            continue  # sem ISIN nem nome → fica avulso (mostrado como ativo próprio no resumo)
        ativo_id = mapa.get(chave)
        if ativo_id is None:
            ativo_id = repo.create(nome=inv.nome or "Renda fixa").id
            mapa[chave] = ativo_id
        inv.ativo_id = ativo_id
    db.commit()
