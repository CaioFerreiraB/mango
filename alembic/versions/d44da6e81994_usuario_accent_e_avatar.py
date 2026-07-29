"""usuario accent e avatar

Revision ID: d44da6e81994
Revises: d4a9c2f10b83
Create Date: 2026-07-15 18:53:55.501503

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd44da6e81994'
down_revision: Union[str, Sequence[str], None] = 'd4a9c2f10b83'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Ruído do autogenerate (VARCHAR(8)→String(16) em categoria_id/pluggy_id) removido — drift conhecido.
    with op.batch_alter_table('usuario', schema=None) as batch_op:
        batch_op.add_column(sa.Column('accent', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('avatar', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('usuario', schema=None) as batch_op:
        batch_op.drop_column('avatar')
        batch_op.drop_column('accent')
