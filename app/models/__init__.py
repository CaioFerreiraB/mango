"""Agrega toda a metadata dos models (import explícito p/ autogenerate do Alembic)."""

from app.db.base import Base
from app.models import (  # noqa: F401
    assinatura,
    ativo,
    cartao_fatura,
    categoria,
    configuracao,
    conta,
    convite,
    divisao,
    fii_fundamento,
    fonte_de_renda,
    investimento,
    investimento_saldo_diario,
    objetivo,
    orcamento,
    pluggy,
    saldo_diario,
    telegram,
    transacao,
    usuario,
)

__all__ = ["Base"]
