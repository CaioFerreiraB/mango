"""Schema do resumo de sincronização (§4.3) — realimenta o toast da UI."""

from pydantic import BaseModel


class ResumoSyncRead(BaseModel):
    itens: int
    contas: int
    transacoes: int
    transacoes_novas: int
    investimentos: int
