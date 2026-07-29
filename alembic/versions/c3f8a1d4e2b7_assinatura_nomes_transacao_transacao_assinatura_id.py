"""assinatura.nomes_transacao (aliases) + transacao.assinatura_id (vínculo)

Revision ID: c3f8a1d4e2b7
Revises: b2e7d4a91c05
Create Date: 2026-07-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3f8a1d4e2b7'
down_revision: Union[str, Sequence[str], None] = 'b2e7d4a91c05'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Aliases de nome de transação p/ casar a assinatura no sync/dedup (§4.7). server_default '[]'
    # backfilla linhas existentes; app usa default=list.
    op.add_column(
        'assinatura',
        sa.Column('nomes_transacao', sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    with op.batch_alter_table('transacao', schema=None) as batch_op:
        batch_op.add_column(sa.Column('assinatura_id', sa.Integer(), nullable=True))
        batch_op.create_index(
            batch_op.f('ix_transacao_assinatura_id'), ['assinatura_id'], unique=False
        )
        batch_op.create_foreign_key(
            batch_op.f('fk_transacao_assinatura_id_assinatura'),
            'assinatura',
            ['assinatura_id'],
            ['id'],
            ondelete='SET NULL',
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('transacao', schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f('fk_transacao_assinatura_id_assinatura'), type_='foreignkey'
        )
        batch_op.drop_index(batch_op.f('ix_transacao_assinatura_id'))
        batch_op.drop_column('assinatura_id')
    op.drop_column('assinatura', 'nomes_transacao')
