"""Contratos explícitos da IA e Mini App; segredos nunca aparecem nas leituras."""

from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator


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


# SQLite devolve datetime sem fuso; o browser leria como hora local. Sempre UTC explícito.
Momento = Annotated[datetime, AfterValidator(lambda d: d if d.tzinfo else d.replace(tzinfo=UTC))]


class ConversaIaResumo(Estrito):
    model_config = ConfigDict(extra="forbid", from_attributes=True)
    id: int
    titulo: str
    atualizado_em: Momento


class MensagemIaRead(Estrito):
    model_config = ConfigDict(extra="forbid", from_attributes=True)
    id: int
    papel: Literal["user", "assistant"]
    conteudo: str
    criado_em: Momento


class PropostaIa(Estrito):
    operacao_id: str
    resumo: str
    expira_em: Momento


class ConversaIaRead(ConversaIaResumo):
    mensagens: list[MensagemIaRead]
    proposta: PropostaIa | None
    executando: bool


class ConversaIaUpdate(Estrito):
    titulo: Annotated[str, Field(min_length=1, max_length=120)]


class MensagemIaCreate(Estrito):
    conversa_id: int | None = None
    texto: Annotated[str | None, Field(min_length=1, max_length=16000)] = None
    regenerar: bool = False

    @model_validator(mode="after")
    def _texto_ou_regenerar(self):
        if self.regenerar == bool(self.texto and self.texto.strip()):
            raise ValueError("envie o texto ou peça para regenerar")
        if self.regenerar and self.conversa_id is None:
            raise ValueError("regenerar exige a conversa")
        return self


class ResultadoProposta(Estrito):
    resultado: str
