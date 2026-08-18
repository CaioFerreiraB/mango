"""orcamento/orcamento_mensal ganham tipo (despesa|receita) e orcamento ganha ordem

Revision ID: 5e88ce7ee436
Revises: c1084e6ceddd
Create Date: 2026-08-08 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5e88ce7ee436"
down_revision: Union[str, Sequence[str], None] = "c1084e6ceddd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # `tipo`: toda linha existente hoje é implicitamente despesa (só existia esse fluxo) —
    # nullable=True pra permitir o backfill, depois trava NOT NULL.
    with op.batch_alter_table("orcamento", schema=None) as batch_op:
        batch_op.add_column(sa.Column("tipo", sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column("ordem", sa.Integer(), nullable=True))
    with op.batch_alter_table("orcamento_mensal", schema=None) as batch_op:
        batch_op.add_column(sa.Column("tipo", sa.String(length=16), nullable=True))

    op.execute("UPDATE orcamento SET tipo = 'despesa'")
    op.execute("UPDATE orcamento_mensal SET tipo = 'despesa'")

    # Backfill de `ordem`: contador reiniciado por usuário, ordenado por id (ordem de criação).
    # Loop em Python — volume de dados desse app (pessoal, poucos usuários) não justifica uma
    # window function (portabilidade SQLite/Postgres também fica mais simples assim).
    bind = op.get_bind()
    linhas = bind.execute(
        sa.text("SELECT id, usuario_id FROM orcamento ORDER BY usuario_id, id")
    ).all()
    contadores: dict[int, int] = {}
    for id_, usuario_id in linhas:
        ordem = contadores.get(usuario_id, 0)
        bind.execute(
            sa.text("UPDATE orcamento SET ordem = :ordem WHERE id = :id"),
            {"ordem": ordem, "id": id_},
        )
        contadores[usuario_id] = ordem + 1

    with op.batch_alter_table("orcamento", schema=None) as batch_op:
        batch_op.alter_column("tipo", existing_type=sa.String(length=16), nullable=False)
        batch_op.alter_column("ordem", existing_type=sa.Integer(), nullable=False)
        batch_op.drop_constraint(op.f("uq_orcamento_usuario_id"), type_="unique")
        batch_op.create_unique_constraint(
            op.f("uq_orcamento_usuario_id"), ["usuario_id", "categoria_id", "tipo"]
        )
        batch_op.create_check_constraint("tipo", "tipo IN ('despesa', 'receita')")

    with op.batch_alter_table("orcamento_mensal", schema=None) as batch_op:
        batch_op.alter_column("tipo", existing_type=sa.String(length=16), nullable=False)
        batch_op.drop_constraint(op.f("uq_orcamento_mensal_usuario_id"), type_="unique")
        batch_op.create_unique_constraint(
            op.f("uq_orcamento_mensal_usuario_id"),
            ["usuario_id", "categoria_id", "ano", "mes", "tipo"],
        )
        batch_op.create_check_constraint("tipo", "tipo IN ('despesa', 'receita')")


def downgrade() -> None:
    """Downgrade schema."""
    # Passos separados (um `batch_alter_table` por vez): misturar drop de CHECK/UNIQUE com
    # drop de coluna no mesmo batch confunde a reconstrução de tabela do SQLite (o CHECK
    # antigo, referenciando a coluna, ainda aparece na tabela intermediária).
    with op.batch_alter_table("orcamento_mensal", schema=None) as batch_op:
        batch_op.drop_constraint(op.f("ck_orcamento_mensal_tipo"), type_="check")
    with op.batch_alter_table("orcamento_mensal", schema=None) as batch_op:
        batch_op.drop_constraint(op.f("uq_orcamento_mensal_usuario_id"), type_="unique")
        batch_op.create_unique_constraint(
            op.f("uq_orcamento_mensal_usuario_id"), ["usuario_id", "categoria_id", "ano", "mes"]
        )
    with op.batch_alter_table("orcamento_mensal", schema=None) as batch_op:
        batch_op.drop_column("tipo")

    with op.batch_alter_table("orcamento", schema=None) as batch_op:
        batch_op.drop_constraint(op.f("ck_orcamento_tipo"), type_="check")
    with op.batch_alter_table("orcamento", schema=None) as batch_op:
        batch_op.drop_constraint(op.f("uq_orcamento_usuario_id"), type_="unique")
        batch_op.create_unique_constraint(
            op.f("uq_orcamento_usuario_id"), ["usuario_id", "categoria_id"]
        )
    with op.batch_alter_table("orcamento", schema=None) as batch_op:
        batch_op.drop_column("ordem")
        batch_op.drop_column("tipo")
