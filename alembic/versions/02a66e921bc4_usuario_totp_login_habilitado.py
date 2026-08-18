"""usuario totp login habilitado

Revision ID: 02a66e921bc4
Revises: dbc5cc4bb655
Create Date: 2026-08-17 09:49:53.178878

2FA vira opcional (§5.2, #15): `totp_login_habilitado` é o "quero código no login" do usuário,
independente de ter o 2FA configurado (`totp_secret_cifrado`) — recuperação de senha continua
exigindo o código sempre, essa flag só afeta o login. Backfill: contas existentes hoje sempre têm
`totp_secret_cifrado` preenchido (2FA era obrigatório) e sempre pediam código no login — a flag
nasce `TRUE` só pra quem já tem o secret, preservando o comportamento atual no upgrade.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "02a66e921bc4"
down_revision: Union[str, Sequence[str], None] = "dbc5cc4bb655"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("usuario", schema=None) as batch_op:
        batch_op.add_column(sa.Column("totp_login_habilitado", sa.Boolean(), nullable=True))

    op.execute("UPDATE usuario SET totp_login_habilitado = FALSE")
    op.execute(
        "UPDATE usuario SET totp_login_habilitado = TRUE WHERE totp_secret_cifrado IS NOT NULL"
    )

    with op.batch_alter_table("usuario", schema=None) as batch_op:
        batch_op.alter_column("totp_login_habilitado", existing_type=sa.Boolean(), nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("usuario", schema=None) as batch_op:
        batch_op.drop_column("totp_login_habilitado")
