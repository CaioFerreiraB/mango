"""vínculo manual de instituição + logo

Revision ID: b2e7d4a91c05
Revises: 422451fbb18f
Create Date: 2026-07-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2e7d4a91c05'
down_revision: Union[str, Sequence[str], None] = '422451fbb18f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('instituicao', sa.Column('logo_url', sa.String(length=1024), nullable=True))
    with op.batch_alter_table('conta', schema=None) as batch_op:
        batch_op.add_column(sa.Column('instituicao_manual_id', sa.Integer(), nullable=True))
        batch_op.create_index(
            batch_op.f('ix_conta_instituicao_manual_id'), ['instituicao_manual_id'], unique=False
        )
        batch_op.create_foreign_key(
            batch_op.f('fk_conta_instituicao_manual_id_instituicao'),
            'instituicao',
            ['instituicao_manual_id'],
            ['id'],
            ondelete='SET NULL',
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('conta', schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f('fk_conta_instituicao_manual_id_instituicao'), type_='foreignkey'
        )
        batch_op.drop_index(batch_op.f('ix_conta_instituicao_manual_id'))
        batch_op.drop_column('instituicao_manual_id')
    op.drop_column('instituicao', 'logo_url')
