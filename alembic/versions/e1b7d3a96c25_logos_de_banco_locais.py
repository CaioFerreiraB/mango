"""Logos de banco servidos pela própria origem

Os logos do catálogo curado apontavam para CDN externo (cdn.pluggy.ai e o serviço de favicons
do Google), que a CSP (`img-src 'self'`) bloqueia — nenhum aparecia. Agora moram em
`frontend/public/logos/bancos/`; reescreve as instituições já vinculadas à mão.

Revision ID: e1b7d3a96c25
Revises: c4f8a2e61d07
Create Date: 2026-11-26 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e1b7d3a96c25"
down_revision: str | Sequence[str] | None = "c4f8a2e61d07"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Congelado aqui (não importa o catálogo): a migration não pode mudar se o catálogo mudar.
_SVG = (212, 201, 203, 208, 226, 291)
_PNG = range(90001, 90016)


def upgrade() -> None:
    sql = sa.text(
        "UPDATE instituicao SET logo_url = :novo "
        "WHERE pluggy_connector_id = :cid AND logo_url LIKE 'https://%'"
    )
    for cid in _SVG:
        op.execute(sql.bindparams(novo=f"/logos/bancos/{cid}.svg", cid=cid))
    for cid in _PNG:
        op.execute(sql.bindparams(novo=f"/logos/bancos/{cid}.png", cid=cid))


def downgrade() -> None:
    # Voltar às URLs externas só reintroduziria logos bloqueados pela CSP.
    pass
