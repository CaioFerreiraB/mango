"""Configuração global da instância (§4.11-otimização) — linha única (id=1), sem `UserOwnedMixin`
(não é posse de ninguém, é da instância inteira). Get-or-create fica no repositório
(`app/repositories/configuracao.py`).
"""

from sqlalchemy import Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class ConfiguracaoSistema(TimestampMixin, Base):
    __tablename__ = "configuracao_sistema"

    id: Mapped[int] = mapped_column(primary_key=True)
    otimizar_transacoes_divisao: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
