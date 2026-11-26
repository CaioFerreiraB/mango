"""Accent: verde → lima, manga → tangerina, teal → grafite

Os presets de cor foram redesenhados (as cores vivas ganham texto escuro por cima); os ids
antigos deixam de existir. Converte a preferência já gravada de cada usuário.

Revision ID: c4f8a2e61d07
Revises: a7e3c5d19b42
Create Date: 2026-11-26 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4f8a2e61d07"
down_revision: str | Sequence[str] | None = "a7e3c5d19b42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NOVOS = {"verde": "lima", "manga": "tangerina", "teal": "grafite"}


def _renomear(de_para: dict[str, str]) -> None:
    for antigo, novo in de_para.items():
        op.execute(f"UPDATE usuario SET accent = '{novo}' WHERE accent = '{antigo}'")


def upgrade() -> None:
    _renomear(_NOVOS)


def downgrade() -> None:
    _renomear({novo: antigo for antigo, novo in _NOVOS.items()})
