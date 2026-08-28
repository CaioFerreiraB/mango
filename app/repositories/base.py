"""Repositório base com isolamento por usuário (§5.2).

INVARIANTE DE SEGURANÇA: toda leitura/escrita é filtrada por `usuario_id`. Um repositório
ligado ao usuário B nunca enxerga nem altera linhas do usuário A — base dos testes de
isolamento. `categoria` é a única fora deste padrão: mistura linha global (`usuario_id` NULL,
taxonomia do Pluggy) com linha do usuário (categoria personalizada), e aplica o escopo à mão em
`app/repositories/categoria.py`.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import Base


class UserScopedRepository[ModelT: Base]:
    model: type[ModelT]
    # Coluna de posse usada no filtro (default `usuario_id`; `divisao_despesa` usa o criador).
    scope_column: str = "usuario_id"

    def __init__(self, db: Session, usuario_id: int) -> None:
        self.db = db
        self.usuario_id = usuario_id

    def _scope(self):
        return getattr(self.model, self.scope_column)

    def _scoped(self):
        return select(self.model).where(self._scope() == self.usuario_id)

    def list(self) -> list[ModelT]:
        return list(self.db.scalars(self._scoped()).all())

    def get(self, obj_id: int) -> ModelT | None:
        return self.db.scalars(self._scoped().where(self.model.id == obj_id)).first()

    def create(self, **fields) -> ModelT:
        obj = self.model(**{self.scope_column: self.usuario_id}, **fields)
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def update(self, obj: ModelT, **fields) -> ModelT:
        for key, value in fields.items():
            setattr(obj, key, value)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def delete(self, obj: ModelT) -> None:
        self.db.delete(obj)
        self.db.commit()
