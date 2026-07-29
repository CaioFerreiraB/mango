"""ativo (agrupa compras de renda fixa) + investimento.ativo_id + transacao.investimento_transacao_id

Revision ID: f2b8c1a4d7e9
Revises: e7c1a5b93f24
Create Date: 2026-07-25 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2b8c1a4d7e9'
down_revision: Union[str, Sequence[str], None] = 'e7c1a5b93f24'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Escrito à mão (o autogenerate re-detecta o ruído VARCHAR(8)→String(16) em
    # categoria_id/pluggy_id — removido de propósito, como nas migrations anteriores).
    op.create_table(
        'ativo',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nome', sa.String(length=255), nullable=False),
        sa.Column('usuario_id', sa.Integer(), nullable=False),
        sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuario.id'], name=op.f('fk_ativo_usuario_id_usuario'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_ativo')),
    )
    with op.batch_alter_table('ativo', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_ativo_usuario_id'), ['usuario_id'], unique=False)

    with op.batch_alter_table('investimento', schema=None) as batch_op:
        batch_op.add_column(sa.Column('ativo_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_investimento_ativo_id'), ['ativo_id'], unique=False)
        batch_op.create_foreign_key(
            batch_op.f('fk_investimento_ativo_id_ativo'), 'ativo', ['ativo_id'], ['id'], ondelete='SET NULL'
        )

    with op.batch_alter_table('transacao', schema=None) as batch_op:
        batch_op.add_column(sa.Column('investimento_transacao_id', sa.Integer(), nullable=True))
        batch_op.create_index(
            batch_op.f('ix_transacao_investimento_transacao_id'), ['investimento_transacao_id'], unique=False
        )
        batch_op.create_foreign_key(
            batch_op.f('fk_transacao_investimento_transacao_id_investimento_transacao'),
            'investimento_transacao',
            ['investimento_transacao_id'],
            ['id'],
            ondelete='SET NULL',
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('transacao', schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f('fk_transacao_investimento_transacao_id_investimento_transacao'), type_='foreignkey'
        )
        batch_op.drop_index(batch_op.f('ix_transacao_investimento_transacao_id'))
        batch_op.drop_column('investimento_transacao_id')

    with op.batch_alter_table('investimento', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_investimento_ativo_id_ativo'), type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_investimento_ativo_id'))
        batch_op.drop_column('ativo_id')

    with op.batch_alter_table('ativo', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_ativo_usuario_id'))
    op.drop_table('ativo')
