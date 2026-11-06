"""Alerta de orçamento no Telegram: % por usuário + switch por categoria + dedupe mensal

Revision ID: e4a7c2b91d05
Revises: d73b915eaf02
Create Date: 2026-11-06 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e4a7c2b91d05"
down_revision: str | Sequence[str] | None = "d73b915eaf02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Nullable → backfill portável (SQLite/Postgres) → NOT NULL, mesmo padrão de `suprimido`.
    with op.batch_alter_table("usuario", schema=None) as batch_op:
        batch_op.add_column(sa.Column("orcamento_alerta_pct", sa.Integer(), nullable=True))
    op.execute("UPDATE usuario SET orcamento_alerta_pct = 80")
    with op.batch_alter_table("usuario", schema=None) as batch_op:
        batch_op.alter_column("orcamento_alerta_pct", existing_type=sa.Integer(), nullable=False)
        batch_op.create_check_constraint(
            "orcamento_alerta_pct", "orcamento_alerta_pct BETWEEN 1 AND 100"
        )

    with op.batch_alter_table("orcamento", schema=None) as batch_op:
        batch_op.add_column(sa.Column("notificar", sa.Boolean(), nullable=True))
    op.execute("UPDATE orcamento SET notificar = true")
    with op.batch_alter_table("orcamento", schema=None) as batch_op:
        batch_op.alter_column("notificar", existing_type=sa.Boolean(), nullable=False)

    with op.batch_alter_table("orcamento_mensal", schema=None) as batch_op:
        batch_op.add_column(sa.Column("notificar", sa.Boolean(), nullable=True))
        batch_op.add_column(
            sa.Column("alerta_enviado_em", sa.DateTime(timezone=True), nullable=True)
        )
    op.execute("UPDATE orcamento_mensal SET notificar = true")
    with op.batch_alter_table("orcamento_mensal", schema=None) as batch_op:
        batch_op.alter_column("notificar", existing_type=sa.Boolean(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("orcamento_mensal", schema=None) as batch_op:
        batch_op.drop_column("alerta_enviado_em")
        batch_op.drop_column("notificar")
    with op.batch_alter_table("orcamento", schema=None) as batch_op:
        batch_op.drop_column("notificar")
    with op.batch_alter_table("usuario", schema=None) as batch_op:
        batch_op.drop_constraint(op.f("ck_usuario_orcamento_alerta_pct"), type_="check")
        batch_op.drop_column("orcamento_alerta_pct")
