"""vínculo manual de instituição passa de conta para item_pluggy (conexão)

Revision ID: 9d4b7c1e3a56
Revises: 7a3e9c1f5b2d
Create Date: 2026-08-16 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9d4b7c1e3a56"
down_revision: Union[str, Sequence[str], None] = "7a3e9c1f5b2d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("item_pluggy", schema=None) as batch_op:
        batch_op.add_column(sa.Column("instituicao_manual_id", sa.Integer(), nullable=True))
        batch_op.create_index(
            batch_op.f("ix_item_pluggy_instituicao_manual_id"),
            ["instituicao_manual_id"],
            unique=False,
        )
        batch_op.create_foreign_key(
            batch_op.f("fk_item_pluggy_instituicao_manual_id_instituicao"),
            "instituicao",
            ["instituicao_manual_id"],
            ["id"],
            ondelete="SET NULL",
        )
    with op.batch_alter_table("conta", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_conta_instituicao_manual_id_instituicao"), type_="foreignkey"
        )
        batch_op.drop_index(batch_op.f("ix_conta_instituicao_manual_id"))
        batch_op.drop_column("instituicao_manual_id")


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("conta", schema=None) as batch_op:
        batch_op.add_column(sa.Column("instituicao_manual_id", sa.Integer(), nullable=True))
        batch_op.create_index(
            batch_op.f("ix_conta_instituicao_manual_id"), ["instituicao_manual_id"], unique=False
        )
        batch_op.create_foreign_key(
            batch_op.f("fk_conta_instituicao_manual_id_instituicao"),
            "instituicao",
            ["instituicao_manual_id"],
            ["id"],
            ondelete="SET NULL",
        )
    with op.batch_alter_table("item_pluggy", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_item_pluggy_instituicao_manual_id_instituicao"), type_="foreignkey"
        )
        batch_op.drop_index(batch_op.f("ix_item_pluggy_instituicao_manual_id"))
        batch_op.drop_column("instituicao_manual_id")
