"""Repositórios de despesa fixa e de seus vencimentos (docs/dev/despesas-fixas.md)."""

from app.models.despesa_fixa import DespesaFixa, DespesaFixaOcorrencia
from app.repositories.base import UserScopedRepository


class DespesaFixaRepository(UserScopedRepository[DespesaFixa]):
    model = DespesaFixa


class OcorrenciaRepository(UserScopedRepository[DespesaFixaOcorrencia]):
    model = DespesaFixaOcorrencia
