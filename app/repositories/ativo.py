"""Repositório de `ativo` (entidade do usuário): CRUD via `UserScopedRepository`."""

from app.models.ativo import Ativo
from app.repositories.base import UserScopedRepository


class AtivoRepository(UserScopedRepository[Ativo]):
    model = Ativo
