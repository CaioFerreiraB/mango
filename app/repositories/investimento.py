"""Repositório de investimento (Pluggy-owned): read/narrow + upsert do sync (Fase 1)."""

from app.models.investimento import Investimento
from app.repositories.base import UserScopedRepository


class InvestimentoRepository(UserScopedRepository[Investimento]):
    model = Investimento

    def get_by_pluggy_id(self, pluggy_investment_id: str) -> Investimento | None:
        return self.db.scalars(
            self._scoped().where(Investimento.pluggy_investment_id == pluggy_investment_id)
        ).first()

    def upsert_by_pluggy_id(self, pluggy_investment_id: str, **fields) -> Investimento:
        obj = self.get_by_pluggy_id(pluggy_investment_id)
        if obj is None:
            return self.create(pluggy_investment_id=pluggy_investment_id, **fields)
        # re-sync NÃO sobrescreve os vínculos do usuário (objetivo_id #4; ativo_id do agrupamento).
        fields.pop("objetivo_id", None)
        fields.pop("ativo_id", None)
        return self.update(obj, **fields)
