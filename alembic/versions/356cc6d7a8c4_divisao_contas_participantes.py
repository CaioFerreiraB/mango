"""divisao_despesa vira cabeçalho + divisao_participante (N-a-N) + convite_usuario

Revision ID: 356cc6d7a8c4
Revises: 920182747ab3
Create Date: 2026-08-09 12:44:24.790057

`divisao_despesa` era pareada (`outro_usuario_id`, uma contraparte); vira cabeçalho +
`divisao_participante` (N pessoas), com "quem pagou" em campo próprio. Sem dado real em produção
até aqui (a tela nunca saiu do placeholder) — ainda assim faz backfill defensivo p/ quem tiver
mexido na API manualmente (Swagger). O CHECK de `modo_divisao` é trocado num batch isolado do
drop de coluna — misturar os dois no mesmo batch confunde a reconstrução de tabela do SQLite
(mesmo cuidado de 5e88ce7ee436/920182747ab3).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "356cc6d7a8c4"
down_revision: Union[str, Sequence[str], None] = "920182747ab3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "convite_usuario",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("criado_por_usuario_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expira_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("usado_em", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["criado_por_usuario_id"],
            ["usuario.id"],
            name=op.f("fk_convite_usuario_criado_por_usuario_id_usuario"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuario.id"],
            name=op.f("fk_convite_usuario_usuario_id_usuario"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_convite_usuario")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_convite_usuario_token_hash")),
    )
    with op.batch_alter_table("convite_usuario", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_convite_usuario_criado_por_usuario_id"),
            ["criado_por_usuario_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_convite_usuario_usuario_id"), ["usuario_id"], unique=False
        )

    op.create_table(
        "divisao_participante",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("divisao_id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("valor_centavos", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["divisao_id"],
            ["divisao_despesa.id"],
            name=op.f("fk_divisao_participante_divisao_id_divisao_despesa"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuario.id"],
            name=op.f("fk_divisao_participante_usuario_id_usuario"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_divisao_participante")),
        sa.UniqueConstraint(
            "divisao_id", "usuario_id", name=op.f("uq_divisao_participante_divisao_id")
        ),
    )
    with op.batch_alter_table("divisao_participante", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_divisao_participante_divisao_id"), ["divisao_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_divisao_participante_usuario_id"), ["usuario_id"], unique=False
        )

    # CHECK antigo (4 modos pareados) sai isolado, antes de qualquer drop de coluna.
    with op.batch_alter_table("divisao_despesa", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("ck_divisao_despesa_modo_divisao"), type_="check")

    with op.batch_alter_table("divisao_despesa", schema=None) as batch_op:
        batch_op.add_column(sa.Column("pago_por_usuario_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("valor_total_centavos", sa.BigInteger(), nullable=True))
        batch_op.add_column(sa.Column("arquivada", sa.Boolean(), nullable=True))

    # Backfill defensivo: pagador = quem criou; total = valor antigo; modo pareado -> novo par.
    # Quem tinha "outro pagou" perde a contraparte no rateio (não virava participante) — aceitável,
    # a feature nunca saiu do placeholder.
    op.execute("UPDATE divisao_despesa SET pago_por_usuario_id = criado_por_usuario_id")
    op.execute("UPDATE divisao_despesa SET valor_total_centavos = valor_centavos")
    # `FALSE` (não `0`): Postgres não faz cast implícito de integer pra boolean (SQLite aceita
    # os dois, por isso só apareceu ao testar em Postgres de verdade).
    op.execute("UPDATE divisao_despesa SET arquivada = FALSE")
    op.execute(
        "UPDATE divisao_despesa SET modo_divisao = 'integral' "
        "WHERE modo_divisao IN ('pago_mim_recebo', 'pago_outro_recebo')"
    )
    op.execute(
        "UPDATE divisao_despesa SET modo_divisao = 'igualmente' "
        "WHERE modo_divisao IN ('pago_mim_dividir', 'pago_outro_dividir')"
    )

    with op.batch_alter_table("divisao_despesa", schema=None) as batch_op:
        batch_op.alter_column("pago_por_usuario_id", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column("valor_total_centavos", existing_type=sa.BigInteger(), nullable=False)
        batch_op.alter_column("arquivada", existing_type=sa.Boolean(), nullable=False)
        batch_op.create_check_constraint(
            "modo_divisao", "modo_divisao IN ('igualmente', 'integral')"
        )
        batch_op.create_index(
            batch_op.f("ix_divisao_despesa_pago_por_usuario_id"),
            ["pago_por_usuario_id"],
            unique=False,
        )
        batch_op.create_foreign_key(
            batch_op.f("fk_divisao_despesa_pago_por_usuario_id_usuario"),
            "usuario",
            ["pago_por_usuario_id"],
            ["id"],
            ondelete="CASCADE",
        )

    with op.batch_alter_table("divisao_despesa", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_divisao_despesa_outro_usuario_id_usuario"), type_="foreignkey"
        )
        batch_op.drop_index(batch_op.f("ix_divisao_despesa_outro_usuario_id"))
        batch_op.drop_column("outro_usuario_id")
        batch_op.drop_column("valor_centavos")


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("divisao_despesa", schema=None) as batch_op:
        batch_op.add_column(sa.Column("valor_centavos", sa.BIGINT(), nullable=True))
        batch_op.add_column(sa.Column("outro_usuario_id", sa.INTEGER(), nullable=True))

    op.execute("UPDATE divisao_despesa SET valor_centavos = valor_total_centavos")
    op.execute(
        "UPDATE divisao_despesa SET outro_usuario_id = pago_por_usuario_id"
    )  # melhor esforço
    op.execute(
        "UPDATE divisao_despesa SET modo_divisao = 'pago_mim_dividir' WHERE modo_divisao = 'igualmente'"
    )
    op.execute(
        "UPDATE divisao_despesa SET modo_divisao = 'pago_mim_recebo' WHERE modo_divisao = 'integral'"
    )

    with op.batch_alter_table("divisao_despesa", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("ck_divisao_despesa_modo_divisao"), type_="check")

    with op.batch_alter_table("divisao_despesa", schema=None) as batch_op:
        batch_op.alter_column("valor_centavos", existing_type=sa.BIGINT(), nullable=False)
        batch_op.alter_column("outro_usuario_id", existing_type=sa.INTEGER(), nullable=False)
        batch_op.create_check_constraint(
            "modo_divisao",
            "modo_divisao IN ('pago_mim_dividir', 'pago_mim_recebo', 'pago_outro_dividir', 'pago_outro_recebo')",
        )
        batch_op.create_index(
            batch_op.f("ix_divisao_despesa_outro_usuario_id"), ["outro_usuario_id"], unique=False
        )
        batch_op.create_foreign_key(
            batch_op.f("fk_divisao_despesa_outro_usuario_id_usuario"),
            "usuario",
            ["outro_usuario_id"],
            ["id"],
            ondelete="CASCADE",
        )

    with op.batch_alter_table("divisao_despesa", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_divisao_despesa_pago_por_usuario_id_usuario"), type_="foreignkey"
        )
        batch_op.drop_index(batch_op.f("ix_divisao_despesa_pago_por_usuario_id"))
        batch_op.drop_column("arquivada")
        batch_op.drop_column("valor_total_centavos")
        batch_op.drop_column("pago_por_usuario_id")

    with op.batch_alter_table("divisao_participante", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_divisao_participante_usuario_id"))
        batch_op.drop_index(batch_op.f("ix_divisao_participante_divisao_id"))
    op.drop_table("divisao_participante")

    with op.batch_alter_table("convite_usuario", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_convite_usuario_usuario_id"))
        batch_op.drop_index(batch_op.f("ix_convite_usuario_criado_por_usuario_id"))
    op.drop_table("convite_usuario")
