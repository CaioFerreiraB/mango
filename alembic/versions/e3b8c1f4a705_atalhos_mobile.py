"""atalhos da barra inferior do celular

Revision ID: e3b8c1f4a705
Revises: d7a1e3c5b902
Create Date: 2026-11-23 18:00:00.000000

- `usuario.atalhos_mobile`: ids dos 3 atalhos escolhidos para a barra inferior do celular (JSON;
  o "Início" é fixo); nulo = padrão do frontend.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e3b8c1f4a705"
down_revision: str | Sequence[str] | None = "d7a1e3c5b902"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("usuario") as b:
        b.add_column(sa.Column("atalhos_mobile", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("usuario") as b:
        b.drop_column("atalhos_mobile")
