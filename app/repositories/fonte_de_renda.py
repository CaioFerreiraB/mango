"""Repositório de `fonte_de_renda` (CRUD do usuário)."""

from app.models.fonte_de_renda import FonteDeRenda
from app.repositories.base import UserScopedRepository


class FonteDeRendaRepository(UserScopedRepository[FonteDeRenda]):
    model = FonteDeRenda
