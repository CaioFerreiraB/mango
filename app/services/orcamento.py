"""Regras de orçamento (§4.6, decisão #20): soma das subcategorias ≤ orçamento da categoria.

A hierarquia vem de `categoria.parent_id`. Validamos nos dois sentidos: ao orçar uma
subcategoria (não estourar o teto do pai) e ao orçar uma categoria (cobrir os filhos já
definidos).
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.categoria import Categoria
from app.models.orcamento import Orcamento
from app.repositories.orcamento import OrcamentoRepository


def _orcamentos_dos_filhos(db: Session, usuario_id: int, pai_id: str) -> dict[str, int]:
    rows = db.execute(
        select(Orcamento.categoria_id, Orcamento.limite_padrao_centavos)
        .join(Categoria, Categoria.pluggy_id == Orcamento.categoria_id)
        .where(Orcamento.usuario_id == usuario_id, Categoria.parent_id == pai_id)
    ).all()
    return {cat_id: limite for cat_id, limite in rows}


def _validar_regra_20(db: Session, usuario_id: int, categoria_id: str, limite: int) -> None:
    categoria = db.get(Categoria, categoria_id)
    if categoria is None:
        raise ValidationError("categoria inexistente")

    # Como subcategoria: a soma com os irmãos não pode exceder o orçamento do pai.
    if categoria.parent_id is not None:
        pai_orc = db.scalars(
            select(Orcamento).where(
                Orcamento.usuario_id == usuario_id,
                Orcamento.categoria_id == categoria.parent_id,
            )
        ).first()
        if pai_orc is not None:
            irmaos = _orcamentos_dos_filhos(db, usuario_id, categoria.parent_id)
            irmaos[categoria_id] = limite  # inclui/atualiza o próprio
            if sum(irmaos.values()) > pai_orc.limite_padrao_centavos:
                raise ValidationError(
                    "soma das subcategorias ultrapassa o orçamento da categoria (#20)"
                )

    # Como categoria-pai: o orçamento deve cobrir a soma dos filhos já orçados.
    filhos = _orcamentos_dos_filhos(db, usuario_id, categoria_id)
    if filhos and sum(filhos.values()) > limite:
        raise ValidationError("orçamento da categoria menor que a soma das subcategorias (#20)")


def criar(db: Session, usuario_id: int, dados: dict) -> Orcamento:
    repo = OrcamentoRepository(db, usuario_id)
    ja_existe = db.scalars(
        select(Orcamento).where(
            Orcamento.usuario_id == usuario_id,
            Orcamento.categoria_id == dados["categoria_id"],
        )
    ).first()
    if ja_existe is not None:
        raise ConflictError("já existe orçamento para esta categoria")
    _validar_regra_20(db, usuario_id, dados["categoria_id"], dados["limite_padrao_centavos"])
    return repo.create(**dados)


def atualizar(db: Session, usuario_id: int, orcamento_id: int, dados: dict) -> Orcamento:
    repo = OrcamentoRepository(db, usuario_id)
    orc = repo.get(orcamento_id)
    if orc is None:
        raise NotFoundError("orçamento não encontrado")
    novo_limite = dados.get("limite_padrao_centavos", orc.limite_padrao_centavos)
    _validar_regra_20(db, usuario_id, orc.categoria_id, novo_limite)
    return repo.update(orc, **dados)
