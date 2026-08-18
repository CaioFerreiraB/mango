"""usuario ganha tipo, ativo e is_admin

Revision ID: 7a3e9c1f5b2d
Revises: 356cc6d7a8c4
Create Date: 2026-08-09 15:00:00.000000

Gestão de usuários em Configurações (§4.11/§5.2): `tipo` distingue conta completa de conta só
divisão de contas (eixo independente de `StatusPessoa`, que é sobre já ter aceitado o convite ou
não); `ativo` bloqueia login/sessão sem apagar histórico; `is_admin` é o dono da instância, único
por instância, quem gerencia os outros usuários. Backfill promove a linha de `usuario` mais antiga
(menor `criado_em`, empate por `id`) a `is_admin=TRUE` — instâncias self-hosted já existentes não
podem ficar sem administrador após o upgrade. Instância nova (tabela vazia) não tem o que
promover: o dono real nasce com `is_admin=True` já em `confirmar_setup`. CHECK de `tipo` isolado do
add/alter de coluna, mesmo cuidado de 356cc6d7a8c4/5e88ce7ee436/920182747ab3.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7a3e9c1f5b2d"
down_revision: Union[str, Sequence[str], None] = "356cc6d7a8c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("usuario", schema=None) as batch_op:
        batch_op.add_column(sa.Column("tipo", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("ativo", sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column("is_admin", sa.Boolean(), nullable=True))

    op.execute("UPDATE usuario SET tipo = 'completo'")
    # `TRUE`/`FALSE` (não `1`/`0`): Postgres não faz cast implícito de integer pra boolean.
    op.execute("UPDATE usuario SET ativo = TRUE")
    op.execute("UPDATE usuario SET is_admin = FALSE")
    op.execute(
        "UPDATE usuario SET is_admin = TRUE WHERE id = "
        "(SELECT id FROM usuario ORDER BY criado_em ASC, id ASC LIMIT 1)"
    )

    with op.batch_alter_table("usuario", schema=None) as batch_op:
        batch_op.alter_column("tipo", existing_type=sa.String(length=20), nullable=False)
        batch_op.alter_column("ativo", existing_type=sa.Boolean(), nullable=False)
        batch_op.alter_column("is_admin", existing_type=sa.Boolean(), nullable=False)
        batch_op.create_check_constraint("tipo", "tipo IN ('completo', 'divisao')")


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("usuario", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("ck_usuario_tipo"), type_="check")

    with op.batch_alter_table("usuario", schema=None) as batch_op:
        batch_op.drop_column("is_admin")
        batch_op.drop_column("ativo")
        batch_op.drop_column("tipo")
