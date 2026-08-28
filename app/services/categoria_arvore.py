"""Navegação da hierarquia de categorias (§4.5).

A taxonomia tem ≤3 níveis e ~130 linhas → resolver em memória é mais simples e mais rápido que um
CTE recursivo, e mantém a paridade SQLite/Postgres. Escopado por usuário: enxerga as globais e as
personalizadas do próprio (que são planas, então cada uma é a própria subárvore).

Usado por dois consumidores: a regra #20 do orçamento (soma das subcategorias ≤ categoria) e a
ativação em cascata — desativar uma raiz desativa os descendentes.
"""

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.categoria import Categoria


def _filhos(db: Session, usuario_id: int) -> dict[str, list[str]]:
    mapa: dict[str, list[str]] = {}
    linhas = db.execute(
        select(Categoria.pluggy_id, Categoria.parent_id).where(
            or_(Categoria.usuario_id.is_(None), Categoria.usuario_id == usuario_id)
        )
    ).all()
    for cid, pid in linhas:
        if pid is not None:
            mapa.setdefault(pid, []).append(cid)
    return mapa


def subarvores(db: Session, usuario_id: int, raizes: set[str]) -> dict[str, set[str]]:
    """Para cada categoria em `raizes`, o conjunto {ela + descendentes}."""
    filhos = _filhos(db, usuario_id)

    def descendentes(raiz: str) -> set[str]:
        vistos = {raiz}
        pilha = [raiz]
        while pilha:
            for f in filhos.get(pilha.pop(), []):
                if f not in vistos:
                    vistos.add(f)
                    pilha.append(f)
        return vistos

    return {r: descendentes(r) for r in raizes}


def com_descendentes(db: Session, usuario_id: int, raiz: str) -> set[str]:
    """{raiz + descendentes} de uma única categoria."""
    return subarvores(db, usuario_id, {raiz})[raiz]
