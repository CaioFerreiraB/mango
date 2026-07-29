"""Repositório de `conta` (Pluggy-owned): read/update estreito + upsert do sync (Fase 1)."""

from app.models.conta import Conta
from app.repositories.base import UserScopedRepository


class ContaRepository(UserScopedRepository[Conta]):
    model = Conta

    def get_by_pluggy_id(self, pluggy_account_id: str) -> Conta | None:
        return self.db.scalars(
            self._scoped().where(Conta.pluggy_account_id == pluggy_account_id)
        ).first()

    def upsert_by_pluggy_id(self, pluggy_account_id: str, **fields) -> Conta:
        """Idempotente por `pluggy_account_id`. O re-sync NÃO sobrescreve campos do
        usuário (`objetivo_id`) — mesma garantia do override de categoria (§4.5)."""
        obj = self.get_by_pluggy_id(pluggy_account_id)
        if obj is None:
            return self.create(pluggy_account_id=pluggy_account_id, **fields)
        fields.pop("objetivo_id", None)
        return self.update(obj, **fields)
