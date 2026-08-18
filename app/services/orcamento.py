"""Regras de orçamento (§4.6, decisão #20): soma das subcategorias ≤ orçamento da categoria.

A hierarquia vem de `categoria.parent_id`. Validamos nos dois sentidos: ao orçar uma
subcategoria (não estourar o teto do pai) e ao orçar uma categoria (cobrir os filhos já
definidos). Sempre escopado por `tipo` — uma árvore de despesa e uma de receita são orçadas
de forma independente (§4.6 + receitas).
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.categoria import Categoria
from app.models.orcamento import Orcamento
from app.repositories.orcamento import OrcamentoRepository


def _orcamentos_dos_filhos(db: Session, usuario_id: int, pai_id: str, tipo: str) -> dict[str, int]:
    rows = db.execute(
        select(Orcamento.categoria_id, Orcamento.limite_padrao_centavos)
        .join(Categoria, Categoria.pluggy_id == Orcamento.categoria_id)
        .where(
            Orcamento.usuario_id == usuario_id,
            Orcamento.tipo == tipo,
            Categoria.parent_id == pai_id,
        )
    ).all()
    return {cat_id: limite for cat_id, limite in rows}


def _validar_regra_20(
    db: Session, usuario_id: int, categoria_id: str, tipo: str, limite: int
) -> None:
    categoria = db.get(Categoria, categoria_id)
    if categoria is None:
        raise ValidationError("categoria inexistente")

    # Como subcategoria: a soma com os irmãos (mesmo tipo) não pode exceder o orçamento do pai.
    if categoria.parent_id is not None:
        pai_orc = db.scalars(
            select(Orcamento).where(
                Orcamento.usuario_id == usuario_id,
                Orcamento.categoria_id == categoria.parent_id,
                Orcamento.tipo == tipo,
            )
        ).first()
        if pai_orc is not None:
            irmaos = _orcamentos_dos_filhos(db, usuario_id, categoria.parent_id, tipo)
            irmaos[categoria_id] = limite  # inclui/atualiza o próprio
            if sum(irmaos.values()) > pai_orc.limite_padrao_centavos:
                raise ValidationError(
                    "soma das subcategorias ultrapassa o orçamento da categoria (#20)"
                )

    # Como categoria-pai: o orçamento deve cobrir a soma dos filhos (mesmo tipo) já orçados.
    filhos = _orcamentos_dos_filhos(db, usuario_id, categoria_id, tipo)
    if filhos and sum(filhos.values()) > limite:
        raise ValidationError("orçamento da categoria menor que a soma das subcategorias (#20)")


def _proximo_ordem(db: Session, usuario_id: int, tipo: str) -> int:
    maior = db.scalar(
        select(func.max(Orcamento.ordem)).where(
            Orcamento.usuario_id == usuario_id, Orcamento.tipo == tipo
        )
    )
    return 0 if maior is None else maior + 1


def criar(db: Session, usuario_id: int, dados: dict) -> Orcamento:
    repo = OrcamentoRepository(db, usuario_id)
    ja_existe = db.scalars(
        select(Orcamento).where(
            Orcamento.usuario_id == usuario_id,
            Orcamento.categoria_id == dados["categoria_id"],
            Orcamento.tipo == dados["tipo"],
        )
    ).first()
    if ja_existe is not None:
        raise ConflictError("já existe orçamento para esta categoria e tipo")
    dados["ordem"] = _proximo_ordem(db, usuario_id, dados["tipo"])  # sempre anexa ao fim
    _validar_regra_20(
        db, usuario_id, dados["categoria_id"], dados["tipo"], dados["limite_padrao_centavos"]
    )
    return repo.create(**dados)


def atualizar(db: Session, usuario_id: int, orcamento_id: int, dados: dict) -> Orcamento:
    repo = OrcamentoRepository(db, usuario_id)
    orc = repo.get(orcamento_id)
    if orc is None:
        raise NotFoundError("orçamento não encontrado")
    novo_limite = dados.get("limite_padrao_centavos", orc.limite_padrao_centavos)
    _validar_regra_20(db, usuario_id, orc.categoria_id, orc.tipo, novo_limite)
    return repo.update(orc, **dados)
