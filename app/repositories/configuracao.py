"""Repositório da configuração global (§4.11-otimização) — linha singleton (id=1).

A migration semeia a linha em produção (boot aplica migrations, `app/main.py`), mas os testes
sobem o schema via `Base.metadata.create_all()` (`tests/conftest.py`), sem rodar
migrations/seeds — por isso `obter()` faz get-or-create, mesmo padrão de
`_get_or_create_local_user` (`app/security/current_user.py`).
"""

from sqlalchemy.orm import Session

from app.models.configuracao import ConfiguracaoSistema


class ConfiguracaoSistemaRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def obter(self) -> ConfiguracaoSistema:
        config = self.db.get(ConfiguracaoSistema, 1)
        if config is None:
            config = ConfiguracaoSistema(id=1)
            self.db.add(config)
            self.db.commit()
            self.db.refresh(config)
        return config
