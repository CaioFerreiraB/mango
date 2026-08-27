"""categoria.icone

Revision ID: 3b7d90c4e152
Revises: 72890a2a6afe
Create Date: 2026-08-27 19:10:00.000000

Ícone da categoria personalizada (§4.5). A categoria do Pluggy tira o ícone dos 2 primeiros
dígitos do `pluggy_id` (raiz da taxonomia, fixa); a criada pelo usuário não tem raiz nenhuma e caía
sempre no ícone genérico — esta coluna é onde a escolha dele fica.

Aditiva e nullável: NULL = o usuário não escolheu, o cliente cai no padrão. Sem CHECK — a allowlist
de nomes vive na fronteira (`app/enums.ICONE_CATEGORIA`), para crescer o catálogo sem migration.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3b7d90c4e152"
down_revision: Union[str, Sequence[str], None] = "72890a2a6afe"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("categoria", schema=None) as batch_op:
        batch_op.add_column(sa.Column("icone", sa.String(length=40), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("categoria", schema=None) as batch_op:
        batch_op.drop_column("icone")
