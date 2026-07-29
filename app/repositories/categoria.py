"""Repositório de categoria — referência GLOBAL read-only (sem filtro por usuário, §4.5)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.categoria import Categoria


class CategoriaRepository:
    """Não é UserScoped: a taxonomia é compartilhada por todos os usuários."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list(self) -> list[Categoria]:
        return list(self.db.scalars(select(Categoria).order_by(Categoria.pluggy_id)).all())

    def get(self, pluggy_id: str) -> Categoria | None:
        return self.db.get(Categoria, pluggy_id)

    def upsert(self, pluggy_id: str, **fields) -> Categoria:
        obj = self.db.get(Categoria, pluggy_id)
        if obj is None:
            obj = Categoria(pluggy_id=pluggy_id, **fields)
            self.db.add(obj)
        else:
            for key, value in fields.items():
                setattr(obj, key, value)
        return obj
