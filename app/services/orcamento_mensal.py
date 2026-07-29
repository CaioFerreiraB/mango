"""Materialização de `orcamento_mensal` a partir dos orçamentos recorrentes (§4.6).

Cada mês tem uma linha editável por (usuário, categoria); o default é o `limite_padrao` do
orçamento. Idempotente: **nunca sobrescreve** linha existente (preserva a edição manual do
usuário — `editado_manualmente`). É a base dos alertas de consumo.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.orcamento import Orcamento, OrcamentoMensal


def materializar_mes(db: Session, usuario_id: int, ano: int, mes: int) -> int:
    """Cria as linhas de `orcamento_mensal` do mês para orçamentos recorrentes+ativos que
    ainda não têm uma. Retorna quantas criou. Idempotente e escopado por usuário (§5.2)."""
    orcamentos = db.scalars(
        select(Orcamento).where(
            Orcamento.usuario_id == usuario_id,
            Orcamento.recorrente.is_(True),
            Orcamento.ativo.is_(True),
        )
    ).all()
    if not orcamentos:
        return 0

    ja_materializadas = set(
        db.scalars(
            select(OrcamentoMensal.categoria_id).where(
                OrcamentoMensal.usuario_id == usuario_id,
                OrcamentoMensal.ano == ano,
                OrcamentoMensal.mes == mes,
            )
        ).all()
    )

    criados = 0
    for orc in orcamentos:
        if orc.categoria_id in ja_materializadas:
            continue
        db.add(
            OrcamentoMensal(
                usuario_id=usuario_id,
                orcamento_id=orc.id,
                categoria_id=orc.categoria_id,
                ano=ano,
                mes=mes,
                limite_centavos=orc.limite_padrao_centavos,
                editado_manualmente=False,
            )
        )
        criados += 1
    if criados:
        db.commit()
    return criados
