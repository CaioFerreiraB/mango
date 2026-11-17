"""tentativa_acesso: freio de forca-bruta na autenticacao (login e recuperacao de senha)

Revision ID: f1b7c3d9e240
Revises: a3c9e5f17b42
Create Date: 2026-11-16 16:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f1b7c3d9e240"
down_revision: str | Sequence[str] | None = "a3c9e5f17b42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tentativa_acesso",
        sa.Column("chave", sa.String(length=320), nullable=False),
        sa.Column("falhas", sa.Integer(), nullable=False),
        sa.Column("janela_inicio", sa.DateTime(timezone=True), nullable=False),
        sa.Column("bloqueado_ate", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("chave", name=op.f("pk_tentativa_acesso")),
    )


def downgrade() -> None:
    op.drop_table("tentativa_acesso")
