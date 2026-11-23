"""patrimônio líquido no snapshot de investimento + layout do dashboard

Revision ID: d7a1e3c5b902
Revises: c4e8a2d6f913
Create Date: 2026-11-23 10:00:00.000000

- `investimento_saldo_diario.liquido_centavos`: valor de resgate (bruto − IR − IOF) do dia,
  base da linha "patrimônio líquido". Nulo nos snapshots antigos (o dashboard estima).
- `usuario.dashboard_layout`: ordem/largura/visibilidade dos widgets do dashboard (JSON);
  nulo = layout padrão.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d7a1e3c5b902"
down_revision: str | Sequence[str] | None = "c4e8a2d6f913"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("investimento_saldo_diario") as b:
        b.add_column(sa.Column("liquido_centavos", sa.BigInteger(), nullable=True))
    with op.batch_alter_table("usuario") as b:
        b.add_column(sa.Column("dashboard_layout", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("usuario") as b:
        b.drop_column("dashboard_layout")
    with op.batch_alter_table("investimento_saldo_diario") as b:
        b.drop_column("liquido_centavos")
