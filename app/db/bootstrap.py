"""Boot do banco: aplica migrations e (na Fase 0+) popula a taxonomia de categorias.

Migrations no boot são exigidas pela §5.4 (schema evolui sozinho, idêntico nos dois bancos).
"""

from pathlib import Path

from alembic import command
from alembic.config import Config

from app.config import settings

_BASE_DIR = Path(__file__).resolve().parents[2]


def _alembic_config() -> Config:
    cfg = Config(str(_BASE_DIR / "alembic.ini"))
    # Resolve caminhos por valor absoluto (independe do cwd de quem chama).
    cfg.set_main_option("script_location", str(_BASE_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    return cfg


def run_migrations() -> None:
    command.upgrade(_alembic_config(), "head")


def _exigir_chaves_de_producao() -> None:
    """Guarda de boot (S2/§5.5): no self-hosted, recusa subir com as chaves de dev do repo.

    Rodar com a chave conhecida do repositório permitiria decifrar as credenciais do banco.
    No modo `local` (desktop monousuário) os defaults seguem válidos.
    """
    if settings.app_mode != "self_hosted":
        return
    inseguras = settings.chaves_inseguras()
    if inseguras:
        nomes = ", ".join(inseguras)
        raise RuntimeError(
            f"Recusando iniciar em self_hosted com chave(s) de desenvolvimento: {nomes}. "
            "Defina valores próprios no ambiente do container (ver `make gen-keys`)."
        )


def bootstrap() -> None:
    _exigir_chaves_de_producao()
    if settings.run_migrations_on_boot:
        run_migrations()
    if settings.seed_categorias_on_boot:
        # Seed idempotente; importado tarde p/ rodar só após as migrations.
        from app.seed.categorias import seed_categorias

        seed_categorias()
