"""orcamento_mensal ganha suprimido (remover categoria só do mês, sem mexer no padrão)

Revision ID: 920182747ab3
Revises: 5e88ce7ee436
Create Date: 2026-08-08 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "920182747ab3"
down_revision: Union[str, Sequence[str], None] = "5e88ce7ee436"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("orcamento_mensal", schema=None) as batch_op:
        batch_op.add_column(sa.Column("suprimido", sa.Boolean(), nullable=True))
    op.execute("UPDATE orcamento_mensal SET suprimido = false")  # portável SQLite/Postgres
    with op.batch_alter_table("orcamento_mensal", schema=None) as batch_op:
        batch_op.alter_column("suprimido", existing_type=sa.Boolean(), nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("orcamento_mensal", schema=None) as batch_op:
        batch_op.drop_column("suprimido")
