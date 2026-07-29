"""Visões agregadas de assinaturas (§4.7): total mensal-equivalente, por categoria, vigentes.

Normaliza cada assinatura vigente (`ativa`) para o valor mensal (trimestral/6 meses/anual são
convertidos); `irregular` fica fora do total mensal por não ter cadência definida.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.assinatura import Assinatura
from app.schemas.assinatura import AssinaturaCategoriaTotal, AssinaturaResumoRead

_FATOR_MENSAL = {"mensal": 1, "trimestral": 3, "semestral": 6, "anual": 12}


def _mensal(valor_centavos: int, periodicidade: str) -> int:
    fator = _FATOR_MENSAL.get(periodicidade)
    return valor_centavos // fator if fator else 0  # irregular → fora do total mensal


def resumo(db: Session, usuario_id: int) -> AssinaturaResumoRead:
    ativas = db.scalars(
        select(Assinatura)
        .where(Assinatura.usuario_id == usuario_id, Assinatura.ativa.is_(True))
        .order_by(Assinatura.nome)
    ).all()

    total = 0
    por_categoria: dict[str | None, int] = {}
    for a in ativas:
        mensal = _mensal(a.valor_centavos, a.periodicidade)
        total += mensal
        por_categoria[a.categoria_id] = por_categoria.get(a.categoria_id, 0) + mensal

    return AssinaturaResumoRead(
        total_mensal_centavos=total,
        por_categoria=[
            AssinaturaCategoriaTotal(categoria_id=cat, total_mensal_centavos=val)
            for cat, val in sorted(por_categoria.items(), key=lambda kv: kv[1], reverse=True)
        ],
        vigentes=list(ativas),
    )
