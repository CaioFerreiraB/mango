"""Schemas do acesso MCP (docs/mcp.md). O token em claro só sai em `TokenMcp`, sob pedido."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

EscopoMcp = Literal["leitura", "escrita"]


class AcessoMcpRead(BaseModel):
    configurado: bool  # já gerou token alguma vez (a linha existe)
    ativo: bool
    escopo: EscopoMcp
    prefixo: str | None  # início do token, p/ a UI mostrar mascarado sem revelá-lo
    token_gerado_em: datetime | None
    ultimo_uso_em: datetime | None


class AcessoMcpUpdate(BaseModel):
    ativo: bool | None = None
    escopo: EscopoMcp | None = None


class TokenMcp(BaseModel):
    token: str
