"""Round-trip das migrations (upgrade→downgrade) em SQLite e PostgreSQL (§5.4).

Usa um banco próprio (não o schema dos demais testes) para exercitar a migration real,
não só `create_all`. Garante paridade de dialeto das migrations no CI.
"""

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

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


def test_usuario_tipo_ativo_admin_backfill(migration_url: str) -> None:
    """Instância self-hosted já existente, upgrade de `356cc6d7a8c4` (sem as colunas novas) até
    `head`: só a linha de `usuario` mais antiga (`criado_em`) vira `is_admin=True` — instância não
    pode ficar sem dono após o upgrade. CHECK de `tipo` rejeita valor fora de completo/divisao."""
    eng = create_db_engine(migration_url)
    Base.metadata.drop_all(eng)
    with eng.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))

    cfg = _alembic_config(migration_url)
    command.upgrade(cfg, "356cc6d7a8c4")

    agora = datetime.now(UTC)
    with eng.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO usuario (nome, email, criado_em, atualizado_em) "
                "VALUES (:nome, :email, :criado_em, :criado_em)"
            ),
            [
                {"nome": "Mais antigo", "email": "antigo@mango.test", "criado_em": agora},
                {
                    "nome": "Mais novo",
                    "email": "novo@mango.test",
                    "criado_em": agora + timedelta(hours=1),
                },
            ],
        )

    command.upgrade(cfg, "head")

    with eng.begin() as conn:
        linhas = conn.execute(
            text("SELECT email, tipo, ativo, is_admin FROM usuario ORDER BY criado_em")
        ).all()
        assert [r.email for r in linhas] == ["antigo@mango.test", "novo@mango.test"]
        assert bool(linhas[0].is_admin) is True
        assert bool(linhas[1].is_admin) is False
        assert all(r.tipo == "completo" for r in linhas)
        assert all(bool(r.ativo) is True for r in linhas)

    with pytest.raises(IntegrityError):  # CHECK de `tipo` rejeita valor inválido
        with eng.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO usuario (nome, email, tipo, ativo, is_admin, criado_em, "
                    "atualizado_em) VALUES ('X', 'x@mango.test', 'invalido', "
                    ":ativo, :is_admin, :agora, :agora)"
                ),
                {"ativo": True, "is_admin": False, "agora": agora},
            )

    eng.dispose()


def test_usuario_totp_login_habilitado_backfill(migration_url: str) -> None:
    """Upgrade de `dbc5cc4bb655` (sem `totp_login_habilitado`) até `head`: 2FA era obrigatório
    antes desta migration, então quem já tinha `totp_secret_cifrado` preenchido nasce com a flag
    `TRUE` (preserva o comportamento — login continua pedindo código); quem não tinha, `FALSE`."""
    eng = create_db_engine(migration_url)
    Base.metadata.drop_all(eng)
    with eng.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))

    cfg = _alembic_config(migration_url)
    command.upgrade(cfg, "dbc5cc4bb655")

    agora = datetime.now(UTC)
    with eng.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO usuario (nome, email, tipo, ativo, is_admin, totp_secret_cifrado, "
                "criado_em, atualizado_em) VALUES (:nome, :email, 'completo', TRUE, FALSE, "
                ":totp, :agora, :agora)"
            ),
            [
                {
                    "nome": "Com 2FA",
                    "email": "com2fa@mango.test",
                    "totp": "segredo-cifrado",
                    "agora": agora,
                },
                {"nome": "Sem 2FA", "email": "sem2fa@mango.test", "totp": None, "agora": agora},
            ],
        )

    command.upgrade(cfg, "head")

    with eng.begin() as conn:
        linhas = conn.execute(
            text("SELECT email, totp_login_habilitado FROM usuario ORDER BY email")
        ).all()
        valores = {r.email: bool(r.totp_login_habilitado) for r in linhas}
        assert valores == {"com2fa@mango.test": True, "sem2fa@mango.test": False}

    eng.dispose()
