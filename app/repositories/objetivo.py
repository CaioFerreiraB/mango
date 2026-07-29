"""Repositório de `objetivo` (CRUD do usuário)."""

from app.models.objetivo import Objetivo
from app.repositories.base import UserScopedRepository


class ObjetivoRepository(UserScopedRepository[Objetivo]):
    model = Objetivo
