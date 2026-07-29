"""Round-trip das migrations (upgrade→downgrade) em SQLite e PostgreSQL (§5.4).

Usa um banco próprio (não o schema dos demais testes) para exercitar a migration real,
não só `create_all`. Garante paridade de dialeto das migrations no CI.
"""

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from app.db.base import Base
from app.db.session import create_db_engine

_RAIZ = Path(__file__).resolve().parents[1]
PG_DEFAULT = "postgresql+psycopg://mango:mango@localhost:5432/mango"


def _alembic_config(url: str) -> Config:
    cfg = Config(str(_RAIZ / "alembic.ini"))
    cfg.set_main_option("script_location", str(_RAIZ / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


@pytest.fixture(params=["sqlite", "postgres"])
def migration_url(request: pytest.FixtureRequest, tmp_path) -> str:
    if request.param == "sqlite":
        return f"sqlite:///{tmp_path}/mig.db"
    url = os.environ.get("TEST_DATABASE_URL", PG_DEFAULT)
    eng = create_db_engine(url)
    try:
        with eng.connect():
            pass
    except Exception:
        pytest.skip("Postgres indisponível")
    finally:
        eng.dispose()
    return url


def test_upgrade_e_downgrade(migration_url: str) -> None:
    eng = create_db_engine(migration_url)
    # Estado limpo (remove resíduo de outros testes/runs).
    Base.metadata.drop_all(eng)
    with eng.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))

    cfg = _alembic_config(migration_url)
    command.upgrade(cfg, "head")
    tabelas = set(inspect(eng).get_table_names())
    # Amostra de tabelas-chave de clusters diferentes.
    assert {"usuario", "conta", "transacao", "categoria", "orcamento"} <= tabelas

    command.downgrade(cfg, "base")
    restantes = set(inspect(eng).get_table_names()) - {"alembic_version"}
    assert restantes == set()
    eng.dispose()
