"""investimento.custo_manual_centavos (valor investido informado à mão)

Revision ID: a1c7e5d92f38
Revises: f2b8c1a4d7e9
Create Date: 2026-07-26 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1c7e5d92f38'
down_revision: Union[str, Sequence[str], None] = 'f2b8c1a4d7e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('investimento', schema=None) as batch_op:
        batch_op.add_column(sa.Column('custo_manual_centavos', sa.BigInteger(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('investimento', schema=None) as batch_op:
        batch_op.drop_column('custo_manual_centavos')
