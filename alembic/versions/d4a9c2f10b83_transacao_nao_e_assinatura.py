"""transacao.nao_e_assinatura (flag "não é assinatura")

Revision ID: d4a9c2f10b83
Revises: c3f8a1d4e2b7
Create Date: 2026-07-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4a9c2f10b83'
down_revision: Union[str, Sequence[str], None] = 'c3f8a1d4e2b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Sinal negativo do usuário (§4.7): detecção e sugestões ignoram a transação. server_default false
    # backfilla as linhas existentes; app usa default=False.
    op.add_column(
        'transacao',
        sa.Column(
            'nao_e_assinatura',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('transacao', 'nao_e_assinatura')
