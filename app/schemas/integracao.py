"""Contratos explícitos da IA e Mini App; segredos nunca aparecem nas leituras."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class Estrito(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProvedorAxon(Estrito):
    tipo: Literal["axon"]
    endpoint: str = Field(max_length=1024)
    chave: str | None = Field(default=None, min_length=1, max_length=4096)


class ProvedorOpenai(Estrito):
    tipo: Literal["openai_compatible"]
    endpoint: str = Field(max_length=1024)
    chave: str | None = Field(default=None, min_length=1, max_length=4096)
    modelo: str = Field(min_length=1, max_length=255)


class ConfigIaUpdate(Estrito):
    ativa: bool = False
    provedor: Annotated[ProvedorAxon | ProvedorOpenai, Field(discriminator="tipo")]
    limite_usuario: int = Field(default=50, ge=1, le=10000)
    limite_instancia: int = Field(default=500, ge=1, le=100000)


class ConfigIaRead(Estrito):
    ativa: bool
    provedor: str
    endpoint: str | None
    modelo: str | None
    configurada: bool
    validada: bool
    limite_usuario: int
    limite_instancia: int


class PreferenciaIaUpdate(Estrito):
    ativa: bool


class PreferenciaIaRead(Estrito):
    ativa: bool
    disponivel: bool
    provedor: str


class MiniappConfig(Estrito):
    ativo: bool = False
    url: str | None = Field(default=None, max_length=1024)


class MiniappLogin(Estrito):
    init_data: str = Field(min_length=1, max_length=16384)


class MiniappSessao(Estrito):
    token: str
    expira_em: str
