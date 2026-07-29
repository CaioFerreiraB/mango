"""Ambiente Alembic — URL e metadata vêm da aplicação (fonte única de verdade)."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import settings
from app.models import Base  # importa app.models → carrega toda a metadata
from app.models.types import EncryptedStr

config = context.config

if config.config_file_name is not None:
    # disable_existing_loggers=False: as migrations rodam no boot (bootstrap); o default True
    # desligaria os loggers da app já importados (ex.: "app.sync"), matando nossos logs.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# URL da app (respeita DATABASE_URL do ambiente; idêntico em CLI e boot). Se quem
# chamou já fixou uma url no Config (ex.: teste de migration), respeita-a.
if not config.get_main_option("sqlalchemy.url"):
    config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata


def _render_item(type_, obj, autogen_context):  # noqa: ANN001
    # Colunas cifradas são TEXT no banco — a cifragem é da aplicação, transparente
    # ao schema. Renderiza como sa.Text() p/ a migration não importar código da app.
    if type_ == "type" and isinstance(obj, EncryptedStr):
        return "sa.Text()"
    return False


def _configure_kwargs() -> dict:
    # batch mode torna ALTER possível no SQLite (migrations futuras); compare_type
    # melhora o autogenerate. Idêntico nos dois dialetos.
    return {
        "target_metadata": target_metadata,
        "compare_type": True,
        "render_as_batch": settings.is_sqlite,
        "render_item": _render_item,
    }


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        **_configure_kwargs(),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, **_configure_kwargs())
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
