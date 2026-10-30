"""Telegram v2: sessões, execução e configuração opcionais."""

from alembic import op
import sqlalchemy as sa

revision = "d73b915eaf02"
down_revision = "c21a9e6d7f30"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "config_integracao",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("miniapp_ativo", sa.Boolean(), primary_key=False, nullable=False),
        sa.Column("url", sa.String(length=1024), primary_key=False, nullable=True),
        sa.Column("ia_ativa", sa.Boolean(), primary_key=False, nullable=False),
        sa.Column("provedor", sa.String(length=32), primary_key=False, nullable=False),
        sa.Column("endpoint", sa.String(length=1024), primary_key=False, nullable=True),
        sa.Column("chave", sa.Text(), primary_key=False, nullable=True),
        sa.Column("modelo", sa.String(length=255), primary_key=False, nullable=True),
        sa.Column("limite_usuario", sa.Integer(), primary_key=False, nullable=False),
        sa.Column("limite_instancia", sa.Integer(), primary_key=False, nullable=False),
        sa.Column("validado", sa.Boolean(), primary_key=False, nullable=False),
    )
    op.create_table(
        "preferencia_ia",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("ativa", sa.Boolean(), primary_key=False, nullable=False),
        sa.Column(
            "usuario_id",
            sa.Integer(),
            sa.ForeignKey("usuario.id", ondelete="CASCADE"),
            primary_key=False,
            nullable=False,
        ),
        sa.UniqueConstraint("usuario_id"),
    )
    op.create_index("ix_preferencia_ia_usuario_id", "preferencia_ia", ["usuario_id"], unique=False)
    op.create_table(
        "trabalho_telegram",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("bot_id", sa.String(length=64), primary_key=False, nullable=False),
        sa.Column("update_id", sa.String(length=64), primary_key=False, nullable=False),
        sa.Column("chat_id", sa.String(length=64), primary_key=False, nullable=False),
        sa.Column("evento", sa.Text(), primary_key=False, nullable=True),
        sa.Column("status", sa.String(length=24), primary_key=False, nullable=False),
        sa.Column("erro", sa.String(length=80), primary_key=False, nullable=True),
        sa.Column("ia_aceita", sa.Boolean(), primary_key=False, nullable=False),
        sa.Column(
            "usuario_id",
            sa.Integer(),
            sa.ForeignKey("usuario.id", ondelete="CASCADE"),
            primary_key=False,
            nullable=False,
        ),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            primary_key=False,
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "atualizado_em",
            sa.DateTime(timezone=True),
            primary_key=False,
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("bot_id", "update_id"),
    )
    op.create_index(
        "ix_trabalho_telegram_usuario_id", "trabalho_telegram", ["usuario_id"], unique=False
    )
    op.create_table(
        "credencial_integracao",
        sa.Column("token_hash", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("tipo", sa.String(length=16), primary_key=False, nullable=False),
        sa.Column("escopo", sa.String(length=16), primary_key=False, nullable=False),
        sa.Column("bot_id", sa.String(length=64), primary_key=False, nullable=False),
        sa.Column("telegram_id", sa.String(length=64), primary_key=False, nullable=False),
        sa.Column(
            "trabalho_id",
            sa.Integer(),
            sa.ForeignKey("trabalho_telegram.id", ondelete=None),
            primary_key=False,
            nullable=True,
        ),
        sa.Column("expira_em", sa.DateTime(timezone=True), primary_key=False, nullable=False),
        sa.Column("revogada", sa.Boolean(), primary_key=False, nullable=False),
        sa.Column(
            "usuario_id",
            sa.Integer(),
            sa.ForeignKey("usuario.id", ondelete="CASCADE"),
            primary_key=False,
            nullable=False,
        ),
    )
    op.create_index(
        "ix_credencial_integracao_usuario_id", "credencial_integracao", ["usuario_id"], unique=False
    )
    op.create_table(
        "mensagem_ia",
        sa.Column(
            "trabalho_id",
            sa.Integer(),
            sa.ForeignKey("trabalho_telegram.id", ondelete=None),
            primary_key=False,
            nullable=False,
        ),
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("papel", sa.String(length=16), primary_key=False, nullable=False),
        sa.Column("conteudo", sa.Text(), primary_key=False, nullable=False),
        sa.Column(
            "usuario_id",
            sa.Integer(),
            sa.ForeignKey("usuario.id", ondelete="CASCADE"),
            primary_key=False,
            nullable=False,
        ),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            primary_key=False,
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "atualizado_em",
            sa.DateTime(timezone=True),
            primary_key=False,
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_mensagem_ia_usuario_id", "mensagem_ia", ["usuario_id"], unique=False)
    op.create_table(
        "operacao_integracao",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column(
            "trabalho_id",
            sa.Integer(),
            sa.ForeignKey("trabalho_telegram.id", ondelete=None),
            primary_key=False,
            nullable=True,
        ),
        sa.Column("tipo", sa.String(length=24), primary_key=False, nullable=False),
        sa.Column("status", sa.String(length=24), primary_key=False, nullable=False),
        sa.Column("payload", sa.Text(), primary_key=False, nullable=False),
        sa.Column("resultado", sa.Text(), primary_key=False, nullable=True),
        sa.Column("expira_em", sa.DateTime(timezone=True), primary_key=False, nullable=False),
        sa.Column(
            "usuario_id",
            sa.Integer(),
            sa.ForeignKey("usuario.id", ondelete="CASCADE"),
            primary_key=False,
            nullable=False,
        ),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            primary_key=False,
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "atualizado_em",
            sa.DateTime(timezone=True),
            primary_key=False,
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_operacao_integracao_usuario_id", "operacao_integracao", ["usuario_id"], unique=False
    )


def downgrade():
    op.drop_table("operacao_integracao")
    op.drop_table("mensagem_ia")
    op.drop_table("credencial_integracao")
    op.drop_table("trabalho_telegram")
    op.drop_table("preferencia_ia")
    op.drop_table("config_integracao")
