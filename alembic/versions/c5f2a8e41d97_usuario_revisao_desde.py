"""usuario.revisao_desde

Revision ID: c5f2a8e41d97
Revises: 3b7d90c4e152
Create Date: 2026-08-28 10:00:00.000000

Data de corte da revisão de transações (§4.3). Conectar uma conta no Pluggy traz o histórico
inteiro dela, e toda transação nasce `revisada=false` — o que enche a fila de revisão com anos de
lançamentos passados e deixa o aviso do dashboard permanentemente aceso. Esta coluna é o "a partir
de quando eu me importo" do usuário: a transação anterior à data tem a revisão **ignorada** (sai da
contagem e do filtro de pendentes), mas **não** é marcada como revisada — o dado cru (`revisada`)
continua intacto, e mudar ou limpar a data é reversível na hora.

Aditiva e nulável, sem backfill: NULL = sem corte, todo o histórico pede revisão, que é exatamente
o comportamento anterior a este campo.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c5f2a8e41d97"
down_revision: Union[str, Sequence[str], None] = "3b7d90c4e152"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("usuario", schema=None) as batch_op:
        batch_op.add_column(sa.Column("revisao_desde", sa.Date(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("usuario", schema=None) as batch_op:
        batch_op.drop_column("revisao_desde")
