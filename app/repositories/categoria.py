"""Repositório de categoria — taxonomia global do Pluggy + personalizadas do usuário (§4.5).

INVARIANTE DE SEGURANÇA (S3): `categoria` é a única tabela que mistura linha global (`usuario_id`
NULL, o espelho do Pluggy) com linha de usuário (categoria personalizada). Aqui:

- **leitura** enxerga global + própria (`_visiveis`);
- **escrita** só alcança a própria (`get_personalizada` antes de qualquer update/delete).

Este módulo é o ÚNICO ponto que aplica essa regra — consultar `Categoria` direto em outro lugar
fura o isolamento. O seed usa `upsert_global`, que é deliberadamente uma função à parte.
"""

# Anotações lazy: o método `list` sombreia o builtin nas anotações dos métodos seguintes
# (`-> list[Categoria]` resolveria para o método e estouraria em tempo de import).
from __future__ import annotations

import secrets

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.models.categoria import PREFIXO_PERSONALIZADA, Categoria, CategoriaDesativada
from app.models.orcamento import Orcamento, OrcamentoMensal
from app.services.texto import normalizar_texto

# Tentativas de gerar um id livre. Com 12 hex (2^48) a colisão é desprezível; o laço existe só
# para não transformar um azar em erro 500.
_MAX_TENTATIVAS_ID = 5


def upsert_global(db: Session, pluggy_id: str, **fields) -> Categoria:
    """Upsert de uma linha GLOBAL da taxonomia (só o seed do Pluggy, §4.5).

    Fora do escopo por usuário de propósito: é a única escrita que pode criar/alterar linha com
    `usuario_id` NULL. Não usar em código servido por requisição.
    """
    obj = db.get(Categoria, pluggy_id)
    if obj is None:
        obj = Categoria(pluggy_id=pluggy_id, usuario_id=None, **fields)
        db.add(obj)
    else:
        for key, value in fields.items():
            setattr(obj, key, value)
    return obj


class CategoriaRepository:
    """Escopado por usuário: enxerga a taxonomia global + as categorias que ele criou."""

    def __init__(self, db: Session, usuario_id: int) -> None:
        self.db = db
        self.usuario_id = usuario_id

    # --- leitura -----------------------------------------------------------------------

    def _visiveis(self):
        return select(Categoria).where(
            or_(Categoria.usuario_id.is_(None), Categoria.usuario_id == self.usuario_id)
        )

    def list(self) -> list[Categoria]:
        """Globais + personalizadas do usuário. Personalizadas por último (id começa com 'u',
        que ordena depois dos dígitos), agrupando-as no fim da lista."""
        return list(self.db.scalars(self._visiveis().order_by(Categoria.pluggy_id)).all())

    def get(self, pluggy_id: str) -> Categoria | None:
        """Categoria visível ao usuário (global ou própria). Nunca a personalizada de outro."""
        return self.db.scalars(self._visiveis().where(Categoria.pluggy_id == pluggy_id)).first()

    def get_personalizada(self, pluggy_id: str) -> Categoria | None:
        """Só categoria PRÓPRIA — portão de toda escrita (renomear/remover)."""
        return self.db.scalars(
            select(Categoria).where(
                Categoria.pluggy_id == pluggy_id, Categoria.usuario_id == self.usuario_id
            )
        ).first()

    def listar_personalizadas(self) -> list[Categoria]:
        return list(
            self.db.scalars(
                select(Categoria)
                .where(Categoria.usuario_id == self.usuario_id)
                .order_by(Categoria.description)
            ).all()
        )

    def nome_em_uso(self, nome: str, *, ignorando: str | None = None) -> bool:
        """Já existe categoria personalizada com este nome (sem caixa/acento)? O UNIQUE do banco
        cobre o caso exato; esta checagem é a que o usuário espera ("Pet" vs. "pet")."""
        alvo = normalizar_texto(nome)
        return any(
            normalizar_texto(c.description) == alvo
            for c in self.listar_personalizadas()
            if c.pluggy_id != ignorando
        )

    # --- escrita (só linha do próprio usuário) -----------------------------------------

    def criar_personalizada(self, nome: str, icone: str | None = None) -> Categoria:
        obj = Categoria(
            pluggy_id=self._novo_id(),
            usuario_id=self.usuario_id,
            description=nome,
            description_translated=nome,
            parent_id=None,  # personalizada é plana (nível raiz)
            icone=icone,
        )
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def renomear(self, obj: Categoria, nome: str) -> Categoria:
        obj.description = nome
        obj.description_translated = nome
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def definir_icone(self, obj: Categoria, icone: str) -> Categoria:
        obj.icone = icone
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def remover(self, obj: Categoria) -> None:
        self.db.delete(obj)
        self.db.commit()

    def _novo_id(self) -> str:
        for _ in range(_MAX_TENTATIVAS_ID):
            candidato = f"{PREFIXO_PERSONALIZADA}{secrets.token_hex(6)}"
            if self.db.get(Categoria, candidato) is None:
                return candidato
        raise RuntimeError("não foi possível gerar um id de categoria livre")

    # --- ativação (conjunto de exclusão por usuário) -----------------------------------

    def desativadas(self) -> set[str]:
        """Ids desativados PARA ESTE usuário. Ausência = ativa."""
        return set(
            self.db.scalars(
                select(CategoriaDesativada.categoria_id).where(
                    CategoriaDesativada.usuario_id == self.usuario_id
                )
            ).all()
        )

    def definir_ativa(self, ids: set[str], ativa: bool) -> None:
        """Ativa/desativa um conjunto de categorias de uma vez (a subárvore, §4.5). Idempotente."""
        if not ids:
            return
        if ativa:
            self.db.execute(
                delete(CategoriaDesativada).where(
                    CategoriaDesativada.usuario_id == self.usuario_id,
                    CategoriaDesativada.categoria_id.in_(ids),
                )
            )
        else:
            for categoria_id in sorted(ids - self.desativadas()):
                self.db.add(
                    CategoriaDesativada(usuario_id=self.usuario_id, categoria_id=categoria_id)
                )
        self.db.commit()

    # --- uso em outras entidades (pré-checagem de exclusão) ----------------------------

    def contar_orcamentos(self, pluggy_id: str) -> int:
        """Quantos orçamentos referenciam a categoria. `orcamento`/`orcamento_mensal` têm
        `categoria_id` NOT NULL com ondelete=RESTRICT: apagar sem checar viraria erro 500."""
        total = 0
        for modelo in (Orcamento, OrcamentoMensal):
            total += (
                self.db.scalar(
                    select(func.count())
                    .select_from(modelo)
                    .where(modelo.usuario_id == self.usuario_id, modelo.categoria_id == pluggy_id)
                )
                or 0
            )
        return total
