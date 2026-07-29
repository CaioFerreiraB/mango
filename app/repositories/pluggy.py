"""Repositórios das conexões Pluggy: instituição, credencial, item."""

from app.models.pluggy import CredencialPluggy, Instituicao, ItemPluggy
from app.repositories.base import UserScopedRepository


class InstituicaoRepository(UserScopedRepository[Instituicao]):
    model = Instituicao

    def upsert_by_connector(self, pluggy_connector_id: int, **fields) -> Instituicao:
        existente = self.db.scalars(
            self._scoped().where(Instituicao.pluggy_connector_id == pluggy_connector_id)
        ).first()
        if existente is None:
            return self.create(pluggy_connector_id=pluggy_connector_id, **fields)
        return self.update(existente, **fields)


class CredencialPluggyRepository(UserScopedRepository[CredencialPluggy]):
    model = CredencialPluggy


class ItemPluggyRepository(UserScopedRepository[ItemPluggy]):
    model = ItemPluggy
