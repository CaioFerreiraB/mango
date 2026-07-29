"""Repositório de assinatura (§4.7)."""

from app.models.assinatura import Assinatura
from app.repositories.base import UserScopedRepository


class AssinaturaRepository(UserScopedRepository[Assinatura]):
    model = Assinatura
