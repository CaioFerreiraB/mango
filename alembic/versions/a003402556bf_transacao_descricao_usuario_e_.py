"""transacao descricao_usuario e observacoes

Revision ID: a003402556bf
Revises: 02a66e921bc4
Create Date: 2026-08-24 17:51:05.902572

Descrição própria + observações do usuário na transação (§4.5): `description`/`description_raw` são
do Pluggy e reescritos a cada sync, então o texto do usuário precisa de colunas próprias — como o
par `categoria_override_id`/`categoria_ajustada_usuario`. Aditiva e nullable: sem backfill, sem
reescrita de tabela, e o código antigo convive com o schema novo (as colunas ficam nulas).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a003402556bf"
down_revision: Union[str, Sequence[str], None] = "02a66e921bc4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("transacao", schema=None) as batch_op:
        batch_op.add_column(sa.Column("descricao_usuario", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("observacoes", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("transacao", schema=None) as batch_op:
        batch_op.drop_column("observacoes")
        batch_op.drop_column("descricao_usuario")
