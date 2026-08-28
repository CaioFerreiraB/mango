"""categorias personalizadas, ativacao por usuario e regras de categorizacao

Revision ID: 72890a2a6afe
Revises: a003402556bf
Create Date: 2026-08-27 09:24:51.968705

Abre a categorização para o usuário (§4.5), em quatro mudanças aditivas e nulláveis — sem backfill,
sem reescrita de tabela, e o código antigo convive com o schema novo:

1. `categoria.usuario_id` (nullable) — NULL = taxonomia global do Pluggy (o que já existia),
   preenchido = categoria criada pelo usuário. Ficar na MESMA tabela preserva as 6 FKs que já
   apontam para `categoria.pluggy_id` (transação ×2, assinatura, orçamento ×2, divisão), então
   categoria personalizada funciona nesses módulos com integridade referencial real. O UNIQUE
   (usuario_id, description) dá nome único por usuário e isenta as linhas globais de graça: NULL
   nunca conflita em UNIQUE, nos dois dialetos.
2. `categoria_desativada` — conjunto de exclusão (ausência = ativa). O estado é por usuário e a
   linha de `categoria` é compartilhada, então não caberia como flag na própria categoria; como
   conjunto, também nasce vazio e dispensa default.
3. `regra_categorizacao` — texto + tipo de match (exato|contém) → categoria.
4. `transacao.categoria_regra_id` — categoria derivada da regra que casou, materializada porque
   casar "contém" contra a tabela de regras em toda agregação seria um join com LIKE.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "72890a2a6afe"
down_revision: Union[str, Sequence[str], None] = "a003402556bf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "categoria_desativada",
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("categoria_id", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(
            ["categoria_id"],
            ["categoria.pluggy_id"],
            name=op.f("fk_categoria_desativada_categoria_id_categoria"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuario.id"],
            name=op.f("fk_categoria_desativada_usuario_id_usuario"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("usuario_id", "categoria_id", name=op.f("pk_categoria_desativada")),
    )
    op.create_table(
        "regra_categorizacao",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("texto", sa.String(length=120), nullable=False),
        sa.Column("texto_normalizado", sa.String(length=120), nullable=False),
        sa.Column("tipo_match", sa.String(length=8), nullable=False),
        sa.Column("categoria_id", sa.String(length=16), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "atualizado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "tipo_match IN ('exato', 'contem')", name=op.f("ck_regra_categorizacao_tipo_match")
        ),
        sa.ForeignKeyConstraint(
            ["categoria_id"],
            ["categoria.pluggy_id"],
            name=op.f("fk_regra_categorizacao_categoria_id_categoria"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuario.id"],
            name=op.f("fk_regra_categorizacao_usuario_id_usuario"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_regra_categorizacao")),
        sa.UniqueConstraint(
            "usuario_id",
            "texto_normalizado",
            "tipo_match",
            name=op.f("uq_regra_categorizacao_usuario_id"),
        ),
    )
    with op.batch_alter_table("regra_categorizacao", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_regra_categorizacao_categoria_id"), ["categoria_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_regra_categorizacao_texto_normalizado"),
            ["texto_normalizado"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_regra_categorizacao_usuario_id"), ["usuario_id"], unique=False
        )

    with op.batch_alter_table("categoria", schema=None) as batch_op:
        batch_op.add_column(sa.Column("usuario_id", sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f("ix_categoria_usuario_id"), ["usuario_id"], unique=False)
        batch_op.create_unique_constraint(
            "uq_categoria_usuario_id_description", ["usuario_id", "description"]
        )
        batch_op.create_foreign_key(
            batch_op.f("fk_categoria_usuario_id_usuario"),
            "usuario",
            ["usuario_id"],
            ["id"],
            ondelete="CASCADE",
        )

    with op.batch_alter_table("transacao", schema=None) as batch_op:
        batch_op.add_column(sa.Column("categoria_regra_id", sa.String(length=16), nullable=True))
        batch_op.create_index(
            batch_op.f("ix_transacao_categoria_regra_id"), ["categoria_regra_id"], unique=False
        )
        batch_op.create_foreign_key(
            batch_op.f("fk_transacao_categoria_regra_id_categoria"),
            "categoria",
            ["categoria_regra_id"],
            ["pluggy_id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("transacao", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_transacao_categoria_regra_id_categoria"), type_="foreignkey"
        )
        batch_op.drop_index(batch_op.f("ix_transacao_categoria_regra_id"))
        batch_op.drop_column("categoria_regra_id")

    with op.batch_alter_table("categoria", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("fk_categoria_usuario_id_usuario"), type_="foreignkey")
        batch_op.drop_constraint("uq_categoria_usuario_id_description", type_="unique")
        batch_op.drop_index(batch_op.f("ix_categoria_usuario_id"))
        batch_op.drop_column("usuario_id")

    with op.batch_alter_table("regra_categorizacao", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_regra_categorizacao_usuario_id"))
        batch_op.drop_index(batch_op.f("ix_regra_categorizacao_texto_normalizado"))
        batch_op.drop_index(batch_op.f("ix_regra_categorizacao_categoria_id"))

    op.drop_table("regra_categorizacao")
    op.drop_table("categoria_desativada")
