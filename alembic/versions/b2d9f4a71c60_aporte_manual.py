"""aporte manual: investimento_transacao.manual + remove investimento.custo_manual_centavos

Revision ID: b2d9f4a71c60
Revises: a1c7e5d92f38
Create Date: 2026-07-26 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2d9f4a71c60'
down_revision: Union[str, Sequence[str], None] = 'a1c7e5d92f38'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('investimento_transacao', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('manual', sa.Boolean(), nullable=False, server_default=sa.false())
        )
    with op.batch_alter_table('investimento', schema=None) as batch_op:
        batch_op.drop_column('custo_manual_centavos')


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('investimento', schema=None) as batch_op:
        batch_op.add_column(sa.Column('custo_manual_centavos', sa.BigInteger(), nullable=True))
    with op.batch_alter_table('investimento_transacao', schema=None) as batch_op:
        batch_op.drop_column('manual')
