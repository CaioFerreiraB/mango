"""divisao ligada a transacao + orcamento do tipo investimento

Revision ID: c4e8a2d6f913
Revises: f1b7c3d9e240
Create Date: 2026-11-22 10:00:00.000000

- `divisao_despesa` ganha `data` (backfill `criado_em`), `transacao_id` (FK SET NULL, único) e
  `sem_transacao` ("paguei fora do banco"), com CHECK impedindo os dois ao mesmo tempo.
- `config_telegram.notif_divisoes_pendentes` (seção do relatório diário, ligada por padrão).
- CHECK de `tipo` em `orcamento`/`orcamento_mensal` aceita `investimento`; orçamentos de despesa
  em categoria de investimento (subárvore 03 menos 0306) migram para o tipo novo.
CHECKs trocados em batches isolados (cuidado do SQLite, ver 356cc6d7a8c4).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4e8a2d6f913"
down_revision: str | Sequence[str] | None = "f1b7c3d9e240"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_RAIZ_INVESTIMENTO = "03000000"
_RAIZ_RENDIMENTOS = "03060000"


def _categorias_investimento(conn) -> list[str]:
    filhos: dict[str | None, list[str]] = {}
    for pluggy_id, parent_id in conn.execute(sa.text("SELECT pluggy_id, parent_id FROM categoria")):
        filhos.setdefault(parent_id, []).append(pluggy_id)

    def subarvore(raiz: str) -> set[str]:
        ids, pilha = set(), [raiz]
        while pilha:
            atual = pilha.pop()
            if atual not in ids:
                ids.add(atual)
                pilha.extend(filhos.get(atual, []))
        return ids

    return sorted(subarvore(_RAIZ_INVESTIMENTO) - subarvore(_RAIZ_RENDIMENTOS))


def _trocar_check_tipo(tabela: str, valores: str) -> None:
    with op.batch_alter_table(tabela, schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f(f"ck_{tabela}_tipo"), type_="check")
    with op.batch_alter_table(tabela, schema=None) as batch_op:
        batch_op.create_check_constraint("tipo", f"tipo IN ({valores})")


def upgrade() -> None:
    with op.batch_alter_table("divisao_despesa", schema=None) as batch_op:
        batch_op.add_column(sa.Column("data", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("transacao_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("sem_transacao", sa.Boolean(), nullable=False, server_default=sa.false())
        )
    op.execute("UPDATE divisao_despesa SET data = criado_em")
    with op.batch_alter_table("divisao_despesa", schema=None) as batch_op:
        batch_op.alter_column("data", existing_type=sa.DateTime(timezone=True), nullable=False)
        batch_op.create_foreign_key(
            batch_op.f("fk_divisao_despesa_transacao_id_transacao"),
            "transacao",
            ["transacao_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_unique_constraint(
            batch_op.f("uq_divisao_despesa_transacao_id"), ["transacao_id"]
        )
    with op.batch_alter_table("divisao_despesa", schema=None) as batch_op:
        batch_op.create_check_constraint(
            "vinculo", "NOT (transacao_id IS NOT NULL AND sem_transacao)"
        )

    with op.batch_alter_table("config_telegram", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "notif_divisoes_pendentes", sa.Boolean(), nullable=False, server_default=sa.true()
            )
        )

    for tabela in ("orcamento", "orcamento_mensal"):
        _trocar_check_tipo(tabela, "'despesa', 'receita', 'investimento'")

    conn = op.get_bind()
    ids = _categorias_investimento(conn)
    if ids:
        for tabela in ("orcamento", "orcamento_mensal"):
            conn.execute(
                sa.text(
                    f"UPDATE {tabela} SET tipo = 'investimento' "
                    "WHERE tipo = 'despesa' AND categoria_id IN :ids"
                ).bindparams(sa.bindparam("ids", expanding=True)),
                {"ids": ids},
            )


def downgrade() -> None:
    op.execute("UPDATE orcamento SET tipo = 'despesa' WHERE tipo = 'investimento'")
    op.execute("UPDATE orcamento_mensal SET tipo = 'despesa' WHERE tipo = 'investimento'")
    for tabela in ("orcamento", "orcamento_mensal"):
        _trocar_check_tipo(tabela, "'despesa', 'receita'")

    with op.batch_alter_table("config_telegram", schema=None) as batch_op:
        batch_op.drop_column("notif_divisoes_pendentes")

    with op.batch_alter_table("divisao_despesa", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("ck_divisao_despesa_vinculo"), type_="check")
    with op.batch_alter_table("divisao_despesa", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("uq_divisao_despesa_transacao_id"), type_="unique")
        batch_op.drop_constraint(
            batch_op.f("fk_divisao_despesa_transacao_id_transacao"), type_="foreignkey"
        )
        batch_op.drop_column("sem_transacao")
        batch_op.drop_column("transacao_id")
        batch_op.drop_column("data")
