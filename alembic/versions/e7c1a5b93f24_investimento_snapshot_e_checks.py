"""investimento_saldo_diario + relaxa CHECKs de investimento_transacao (Fase 3)

Revision ID: e7c1a5b93f24
Revises: 89a4ee7d6c0d
Create Date: 2026-07-17 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7c1a5b93f24'
down_revision: Union[str, Sequence[str], None] = '89a4ee7d6c0d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Escrito à mão (o autogenerate re-detecta o ruído VARCHAR(8)→String(16) em
    # categoria_id/pluggy_id — removido de propósito, como na 89a4ee7d6c0d).
    op.create_table(
        'investimento_saldo_diario',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('investimento_id', sa.Integer(), nullable=False),
        sa.Column('data', sa.Date(), nullable=False),
        sa.Column('valor_centavos', sa.BigInteger(), nullable=False),
        sa.Column('usuario_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['investimento_id'], ['investimento.id'], name=op.f('fk_investimento_saldo_diario_investimento_id_investimento'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuario.id'], name=op.f('fk_investimento_saldo_diario_usuario_id_usuario'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_investimento_saldo_diario')),
        sa.UniqueConstraint('investimento_id', 'data', name='uq_investimento_saldo_diario_inv_data'),
    )
    with op.batch_alter_table('investimento_saldo_diario', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_investimento_saldo_diario_investimento_id'), ['investimento_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_investimento_saldo_diario_usuario_id'), ['usuario_id'], unique=False)

    # Proventos reais (DIVIDEND/TRANSFER/…, §4.9) não cabem no CHECK BUY/SELL da Fase 0;
    # campos do Pluggy variam por tipo → string livre nullable (String(32): 'AMORTIZATION'
    # tem 12 chars e o Postgres impõe o limite, ao contrário do SQLite).
    with op.batch_alter_table('investimento_transacao', schema=None) as batch_op:
        batch_op.drop_constraint(op.f('ck_investimento_transacao_type'), type_='check')
        batch_op.drop_constraint(op.f('ck_investimento_transacao_movement_type'), type_='check')
        batch_op.alter_column(
            'type', existing_type=sa.String(length=8), type_=sa.String(length=32), nullable=True
        )
        batch_op.alter_column(
            'movement_type',
            existing_type=sa.String(length=8),
            type_=sa.String(length=32),
            nullable=True,
        )


def downgrade() -> None:
    """Downgrade schema. Falha se houver dados fora de BUY/SELL ou NULL (esperado)."""
    with op.batch_alter_table('investimento_transacao', schema=None) as batch_op:
        batch_op.alter_column(
            'movement_type',
            existing_type=sa.String(length=32),
            type_=sa.String(length=8),
            nullable=False,
        )
        batch_op.alter_column(
            'type', existing_type=sa.String(length=32), type_=sa.String(length=8), nullable=False
        )
        # Nome curto: a naming_convention prefixa ck_<tabela>_ (mesma forma do check_in original).
        batch_op.create_check_constraint('type', "type IN ('BUY', 'SELL')")
        batch_op.create_check_constraint('movement_type', "movement_type IN ('CREDIT', 'DEBIT')")

    with op.batch_alter_table('investimento_saldo_diario', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_investimento_saldo_diario_usuario_id'))
        batch_op.drop_index(batch_op.f('ix_investimento_saldo_diario_investimento_id'))

    op.drop_table('investimento_saldo_diario')
