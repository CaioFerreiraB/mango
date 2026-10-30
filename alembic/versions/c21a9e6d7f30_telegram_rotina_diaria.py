"""Telegram verificado e rotina diária, sem alterar dados financeiros.

Revision ID: c21a9e6d7f30
Revises: fdf48cbfd18b
"""

from alembic import op
import sqlalchemy as sa

revision = "c21a9e6d7f30"
down_revision = "fdf48cbfd18b"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("configuracao_sistema") as batch:
        batch.add_column(sa.Column("telegram_token_cifrado", sa.Text(), nullable=True))
        batch.add_column(sa.Column("telegram_bot_id", sa.String(64), nullable=True))
        batch.add_column(sa.Column("telegram_username", sa.String(255), nullable=True))
        batch.add_column(sa.Column("telegram_ativo", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("telegram_offset", sa.BigInteger(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("telegram_erro", sa.String(80), nullable=True))
        batch.add_column(sa.Column("telegram_url", sa.String(1024), nullable=True))
        batch.add_column(sa.Column("sync_automatico", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("sync_horario", sa.Time(), nullable=False, server_default="08:00:00"))
    # O CRUD antigo aceitava IDs arbitrários; não são prova de posse de uma conta Telegram.
    op.execute(sa.text("UPDATE config_telegram SET chat_id = NULL, ativo = false, notif_nao_revisadas = false"))
    with op.batch_alter_table("config_telegram") as batch:
        for nome, tipo in (
            ("telegram_usuario_id", sa.String(64)), ("telegram_nome", sa.String(255)),
            ("telegram_username", sa.String(255)), ("vinculo_hash", sa.String(64)),
            ("solicitacao_id", sa.String(64)), ("vinculo_expira_em", sa.DateTime(timezone=True)),
            ("candidato_id", sa.String(64)), ("candidato_nome", sa.String(255)),
            ("candidato_username", sa.String(255)), ("ultimo_teste_em", sa.DateTime(timezone=True)),
            ("ultimo_envio_em", sa.DateTime(timezone=True)), ("erro", sa.String(80)),
        ):
            batch.add_column(sa.Column(nome, tipo, nullable=True))
        for campo in ("telegram_usuario_id", "chat_id", "vinculo_hash"):
            batch.create_unique_constraint(f"uq_config_telegram_{campo}", [campo])
    op.create_table(
        "execucao_diaria",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("sync_status", sa.String(20), nullable=False),
        sa.Column("envio_status", sa.String(20), nullable=False),
        sa.Column("tentativas_sync", sa.Integer(), nullable=False),
        sa.Column("tentativas_envio", sa.Integer(), nullable=False),
        sa.Column("proxima_tentativa", sa.DateTime(timezone=True)),
        sa.Column("erro", sa.String(80)),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("usuario_id", "data", name="uq_execucao_diaria_usuario_id"),
    )
    op.create_index("ix_execucao_diaria_usuario_id", "execucao_diaria", ["usuario_id"])


def downgrade():
    op.drop_table("execucao_diaria")
    with op.batch_alter_table("config_telegram") as batch:
        for campo in ("telegram_usuario_id", "chat_id", "vinculo_hash"):
            batch.drop_constraint(f"uq_config_telegram_{campo}", type_="unique")
        for campo in ("telegram_usuario_id", "telegram_nome", "telegram_username", "vinculo_hash", "solicitacao_id", "vinculo_expira_em", "candidato_id", "candidato_nome", "candidato_username", "ultimo_teste_em", "ultimo_envio_em", "erro"):
            batch.drop_column(campo)
    with op.batch_alter_table("configuracao_sistema") as batch:
        for campo in ("telegram_token_cifrado", "telegram_bot_id", "telegram_username", "telegram_ativo", "telegram_offset", "telegram_erro", "telegram_url", "sync_automatico", "sync_horario"):
            batch.drop_column(campo)
