"""Chat web: conversa_ia + execução por mensagem (credencial/operação sem Telegram)

Revision ID: a3c9e5f17b42
Revises: e4a7c2b91d05
Create Date: 2026-11-13 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a3c9e5f17b42"
down_revision: str | Sequence[str] | None = "e4a7c2b91d05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "conversa_ia",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("titulo", sa.Text(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "atualizado_em",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuario.id"],
            name=op.f("fk_conversa_ia_usuario_id_usuario"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conversa_ia")),
    )
    op.create_index(op.f("ix_conversa_ia_usuario_id"), "conversa_ia", ["usuario_id"])

    with op.batch_alter_table("mensagem_ia", schema=None) as batch_op:
        batch_op.alter_column("trabalho_id", existing_type=sa.Integer(), nullable=True)
        batch_op.add_column(sa.Column("conversa_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            batch_op.f("fk_mensagem_ia_conversa_id_conversa_ia"),
            "conversa_ia",
            ["conversa_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_index(batch_op.f("ix_mensagem_ia_conversa_id"), ["conversa_id"])
        batch_op.add_column(sa.Column("chave", sa.String(length=64), nullable=True))
        batch_op.create_unique_constraint(
            batch_op.f("uq_mensagem_ia_usuario_id"), ["usuario_id", "chave"]
        )

    with op.batch_alter_table("credencial_integracao", schema=None) as batch_op:
        batch_op.alter_column("bot_id", existing_type=sa.String(length=64), nullable=True)
        batch_op.alter_column("telegram_id", existing_type=sa.String(length=64), nullable=True)
        batch_op.add_column(sa.Column("mensagem_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            batch_op.f("fk_credencial_integracao_mensagem_id_mensagem_ia"),
            "mensagem_ia",
            ["mensagem_id"],
            ["id"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table("operacao_integracao", schema=None) as batch_op:
        batch_op.add_column(sa.Column("mensagem_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            batch_op.f("fk_operacao_integracao_mensagem_id_mensagem_ia"),
            "mensagem_ia",
            ["mensagem_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    # Linhas exclusivas do chat web não cabem no esquema antigo (colunas NOT NULL do Telegram).
    op.execute("DELETE FROM operacao_integracao WHERE trabalho_id IS NULL AND mensagem_id IS NOT NULL")
    op.execute("DELETE FROM credencial_integracao WHERE bot_id IS NULL OR telegram_id IS NULL")
    op.execute("DELETE FROM mensagem_ia WHERE trabalho_id IS NULL")
    with op.batch_alter_table("operacao_integracao", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_operacao_integracao_mensagem_id_mensagem_ia"), type_="foreignkey"
        )
        batch_op.drop_column("mensagem_id")
    with op.batch_alter_table("credencial_integracao", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_credencial_integracao_mensagem_id_mensagem_ia"), type_="foreignkey"
        )
        batch_op.drop_column("mensagem_id")
        batch_op.alter_column("telegram_id", existing_type=sa.String(length=64), nullable=False)
        batch_op.alter_column("bot_id", existing_type=sa.String(length=64), nullable=False)
    with op.batch_alter_table("mensagem_ia", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("uq_mensagem_ia_usuario_id"), type_="unique")
        batch_op.drop_column("chave")
        batch_op.drop_index(batch_op.f("ix_mensagem_ia_conversa_id"))
        batch_op.drop_constraint(
            batch_op.f("fk_mensagem_ia_conversa_id_conversa_ia"), type_="foreignkey"
        )
        batch_op.drop_column("conversa_id")
        batch_op.alter_column("trabalho_id", existing_type=sa.Integer(), nullable=False)
    op.drop_index(op.f("ix_conversa_ia_usuario_id"), table_name="conversa_ia")
    op.drop_table("conversa_ia")
