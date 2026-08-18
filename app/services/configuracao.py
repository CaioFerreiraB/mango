"""Configuração global da instância (§4.11-otimização)."""

from sqlalchemy.orm import Session

from app.repositories.configuracao import ConfiguracaoSistemaRepository
from app.schemas.configuracao import ConfiguracaoSistemaRead, ConfiguracaoSistemaUpdate


def obter(db: Session) -> ConfiguracaoSistemaRead:
    config = ConfiguracaoSistemaRepository(db).obter()
    return ConfiguracaoSistemaRead.model_validate(config)


def atualizar(db: Session, payload: ConfiguracaoSistemaUpdate) -> ConfiguracaoSistemaRead:
    repo = ConfiguracaoSistemaRepository(db)
    config = repo.obter()
    config.otimizar_transacoes_divisao = payload.otimizar_transacoes_divisao
    db.commit()
    db.refresh(config)
    return ConfiguracaoSistemaRead.model_validate(config)


def otimizacao_divisao_ativa(db: Session) -> bool:
    """Leitura pontual do toggle, usada por `app/services/divisao.py` sem puxar o schema
    inteiro. `divisao` importa `configuracao`, nunca o contrário (evita ciclo)."""
    return ConfiguracaoSistemaRepository(db).obter().otimizar_transacoes_divisao
