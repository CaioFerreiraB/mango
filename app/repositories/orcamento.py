"""Repositórios de orçamento (definição) e orçamento mensal (materializado/editável)."""

from app.models.orcamento import Orcamento, OrcamentoMensal
from app.repositories.base import UserScopedRepository


class OrcamentoRepository(UserScopedRepository[Orcamento]):
    model = Orcamento


class OrcamentoMensalRepository(UserScopedRepository[OrcamentoMensal]):
    model = OrcamentoMensal
