"""Schemas do perfil do usuário (§4.1). Update com campos **explícitos** — nunca
mass-assignment de `senha_hash`/`totp_secret_cifrado`/`usuario_id` (S4)."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas import ORMModel
from app.schemas.setup import _normalizar_email

Accent = Literal["violeta", "manga", "verde", "azul", "rosa", "teal"]


class PerfilRead(ORMModel):
    id: int
    nome: str
    email: str
    data_nascimento: date | None
    salario_mensal_centavos: int | None
    formacao: str | None
    ocupacao: str | None
    accent: Accent | None
    avatar: int | None
    # Corte da fila de revisão (§4.3): null = sem corte, todo o histórico pede revisão.
    revisao_desde: date | None
    # Booleano derivado (o token brapi nunca é devolvido — §5.5).
    brapi_token_configurado: bool
    # 2FA opcional (§5.2, #15): booleanos derivados, o segredo nunca é devolvido.
    totp_configurado: bool
    totp_login_habilitado: bool


class PerfilUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=255)
    email: str | None = None
    data_nascimento: date | None = None
    salario_mensal_centavos: int | None = Field(default=None, ge=0)
    formacao: str | None = Field(default=None, max_length=255)
    ocupacao: str | None = Field(default=None, max_length=255)
    accent: Accent | None = None
    avatar: int | None = Field(default=None, ge=1, le=4)
    revisao_desde: date | None = None

    @field_validator("email")
    @classmethod
    def _valida_email(cls, v: str | None) -> str | None:
        return None if v is None else _normalizar_email(v)


class BrapiTokenSet(BaseModel):
    """Grava o token brapi (write-only, cifrado em repouso). Nunca é lido de volta."""

    token: str = Field(min_length=1, max_length=512)


class BrapiTokenTeste(BaseModel):
    valida: bool


# --- 2FA (§5.2, #15): cadastrar/trocar exige reconfirmar a senha atual (step-up) ---------------


class TotpIniciarRequest(BaseModel):
    senha_atual: str = Field(min_length=1)


class TotpIniciado(BaseModel):
    """Passo 1 de cadastrar/trocar o 2FA — mesmo shape do setup/convite, ticket cifrado."""

    totp_secret: str
    totp_provisioning_uri: str
    ticket: str


class TotpConfirmarRequest(BaseModel):
    ticket: str = Field(min_length=1)
    codigo_totp: str = Field(min_length=6, max_length=8)


class TotpDesabilitarRequest(BaseModel):
    senha_atual: str = Field(min_length=1)
