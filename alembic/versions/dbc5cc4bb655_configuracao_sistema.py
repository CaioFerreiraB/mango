"""configuracao_sistema (otimização de transações de divisão)

Revision ID: dbc5cc4bb655
Revises: 9d4b7c1e3a56
Create Date: 2026-08-16 00:00:00.000000

Tabela singleton (linha única, id=1) pra configurações globais da instância (§4.11-otimização) —
primeira config desse tipo, não existia nenhuma tabela de "configurações do sistema" até aqui.
`otimizar_transacoes_divisao` liga a simplificação de dívidas em cadeia do módulo de divisão de
contas (só o dono da instância pode alterar, via `require_admin`); nasce `TRUE` por decisão de
produto. O repositório (`app/repositories/configuracao.py`) faz get-or-create da linha — a seed
abaixo cobre o caso comum (produção, upgrade via `alembic upgrade head`).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "dbc5cc4bb655"
down_revision: Union[str, Sequence[str], None] = "9d4b7c1e3a56"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "configuracao_sistema",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "otimizar_transacoes_divisao",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "atualizado_em",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        "INSERT INTO configuracao_sistema (id, otimizar_transacoes_divisao) VALUES (1, TRUE)"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("configuracao_sistema")
