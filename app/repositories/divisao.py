"""Repositório de divisão de despesas (§4.11) — posse pelo criador (scope_column)."""

from app.models.divisao import DivisaoDespesa
from app.repositories.base import UserScopedRepository


class DivisaoDespesaRepository(UserScopedRepository[DivisaoDespesa]):
    model = DivisaoDespesa
    scope_column = "criado_por_usuario_id"
