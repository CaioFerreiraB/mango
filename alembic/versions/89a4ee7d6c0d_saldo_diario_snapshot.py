"""saldo_diario snapshot

Revision ID: 89a4ee7d6c0d
Revises: d44da6e81994
Create Date: 2026-07-16 09:53:23.075627

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '89a4ee7d6c0d'
down_revision: Union[str, Sequence[str], None] = 'd44da6e81994'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Só a tabela nova. O autogenerate também re-detecta VARCHAR(8)→String(16) nas FKs
    # categoria_id/pluggy_id — ruído conhecido e inócuo, removido daqui de propósito.
    op.create_table(
        'saldo_diario',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('conta_id', sa.Integer(), nullable=False),
        sa.Column('data', sa.Date(), nullable=False),
        sa.Column('saldo_centavos', sa.BigInteger(), nullable=False),
        sa.Column('usuario_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['conta_id'], ['conta.id'], name=op.f('fk_saldo_diario_conta_id_conta'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuario.id'], name=op.f('fk_saldo_diario_usuario_id_usuario'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_saldo_diario')),
        sa.UniqueConstraint('conta_id', 'data', name='uq_saldo_diario_conta_data'),
    )
    with op.batch_alter_table('saldo_diario', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_saldo_diario_conta_id'), ['conta_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_saldo_diario_usuario_id'), ['usuario_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('saldo_diario', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_saldo_diario_usuario_id'))
        batch_op.drop_index(batch_op.f('ix_saldo_diario_conta_id'))

    op.drop_table('saldo_diario')
