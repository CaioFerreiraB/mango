"""Schemas de fatura/cartão (leitura). Dados do Pluggy."""

from app.models.cartao_fatura import Fatura
from app.schemas.auto import read_model

FaturaRead = read_model(Fatura)
