"""Ativo: vínculo a objetivo pelo investimento inteiro (não por compra)

Backfill: cada ativo herda o objetivo das suas compras já vinculadas (se divergirem, o de maior
saldo) e todas as compras do ativo passam a espelhar esse vínculo.

Revision ID: a7e3c5d19b42
Revises: 47d923596fe8
Create Date: 2026-11-25 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7e3c5d19b42"
down_revision: str | Sequence[str] | None = "47d923596fe8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("ativo", schema=None) as batch_op:
        batch_op.add_column(sa.Column("objetivo_id", sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f("ix_ativo_objetivo_id"), ["objetivo_id"], unique=False)
        batch_op.create_foreign_key(
            batch_op.f("fk_ativo_objetivo_id_objetivo"),
            "objetivo",
            ["objetivo_id"],
            ["id"],
            ondelete="SET NULL",
        )

    op.execute(
        """
        UPDATE ativo SET objetivo_id = (
            SELECT i.objetivo_id FROM investimento i
            WHERE i.ativo_id = ativo.id AND i.objetivo_id IS NOT NULL
            GROUP BY i.objetivo_id
            ORDER BY SUM(i.saldo_centavos) DESC, i.objetivo_id
            LIMIT 1
        )
        """
    )
    op.execute(
        """
        UPDATE investimento SET objetivo_id = (
            SELECT a.objetivo_id FROM ativo a WHERE a.id = investimento.ativo_id
        )
        WHERE ativo_id IS NOT NULL
        """
    )


def downgrade() -> None:
    with op.batch_alter_table("ativo", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("fk_ativo_objetivo_id_objetivo"), type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_ativo_objetivo_id"))
        batch_op.drop_column("objetivo_id")
