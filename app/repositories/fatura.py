"""Repositório de fatura (Pluggy-owned): read + upsert do sync (Fase 1)."""

from app.models.cartao_fatura import Fatura
from app.repositories.base import UserScopedRepository


class FaturaRepository(UserScopedRepository[Fatura]):
    model = Fatura

    def upsert_by_pluggy_id(self, pluggy_bill_id: str, **fields) -> Fatura:
        obj = self.db.scalars(self._scoped().where(Fatura.pluggy_bill_id == pluggy_bill_id)).first()
        if obj is None:
            return self.create(pluggy_bill_id=pluggy_bill_id, **fields)
        return self.update(obj, **fields)
