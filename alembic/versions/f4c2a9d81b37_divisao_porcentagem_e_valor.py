"""divisão por porcentagem e por valor

Revision ID: f4c2a9d81b37
Revises: e3b8c1f4a705
Create Date: 2026-11-24 12:00:00.000000

- `divisao_despesa.modo_divisao` aceita `porcentagem` e `valor` (CHECK recriado).
- `divisao_participante.percentual_bp`: fatia em centésimos de ponto percentual (modo
  `porcentagem`); nulo nos demais modos.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f4c2a9d81b37"
down_revision: str | Sequence[str] | None = "e3b8c1f4a705"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NOVO = "modo_divisao IN ('igualmente', 'integral', 'porcentagem', 'valor')"
_ANTIGO = "modo_divisao IN ('igualmente', 'integral')"


def _trocar_check(expressao: str) -> None:
    # Um `batch_alter_table` por passo: drop e create do mesmo CHECK no mesmo batch confundem a
    # recriação da tabela no SQLite (mesmo cuidado de 5e88ce7ee436).
    with op.batch_alter_table("divisao_despesa") as b:
        b.drop_constraint(op.f("ck_divisao_despesa_modo_divisao"), type_="check")
    with op.batch_alter_table("divisao_despesa") as b:
        b.create_check_constraint("modo_divisao", expressao)


def upgrade() -> None:
    _trocar_check(_NOVO)
    with op.batch_alter_table("divisao_participante") as b:
        b.add_column(sa.Column("percentual_bp", sa.Integer(), nullable=True))


def downgrade() -> None:
    # Divisões nos modos novos não cabem no CHECK antigo e convertê-las perderia o rateio: recusa
    # o downgrade enquanto existirem (antes de mexer em qualquer coisa).
    restantes = op.get_bind().scalar(
        sa.text(
            "SELECT count(*) FROM divisao_despesa WHERE modo_divisao IN ('porcentagem', 'valor')"
        )
    )
    if restantes:
        raise RuntimeError(f"{restantes} divisão(ões) por porcentagem/valor impedem o downgrade")
    with op.batch_alter_table("divisao_participante") as b:
        b.drop_column("percentual_bp")
    _trocar_check(_ANTIGO)
