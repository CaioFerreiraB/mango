"""Repositório de `regra_categorizacao` (§4.5). Isolado por `usuario_id` como todo o resto."""

from sqlalchemy import func, select

from app.models.categoria import RegraCategorizacao
from app.repositories.base import UserScopedRepository


class RegraCategorizacaoRepository(UserScopedRepository[RegraCategorizacao]):
    model = RegraCategorizacao

    def contar(self) -> int:
        return (
            self.db.scalar(
                select(func.count())
                .select_from(RegraCategorizacao)
                .where(RegraCategorizacao.usuario_id == self.usuario_id)
            )
            or 0
        )

    def por_chave(self, texto_normalizado: str, tipo_match: str) -> RegraCategorizacao | None:
        """Regra com o mesmo texto normalizado e tipo — o que o UNIQUE do banco também impede."""
        return self.db.scalars(
            self._scoped().where(
                RegraCategorizacao.texto_normalizado == texto_normalizado,
                RegraCategorizacao.tipo_match == tipo_match,
            )
        ).first()
