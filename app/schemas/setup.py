"""Schemas do first-run setup (§4.1, §4.3, #15).

Segredos (senha, Pluggy) entram em claro e nunca saem: `SetupResult` só devolve o material do
TOTP (segredo + URI de provisionamento) para o usuário escanear o QR uma única vez.
"""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel, Field, field_validator


def _normalizar_email(v: str) -> str:
    v = v.strip().lower()
    if "@" not in v or "." not in v.split("@")[-1]:
        raise ValueError("e-mail inválido")
    return v


class PluggyCredenciais(BaseModel):
    client_id: str = Field(min_length=1)
    client_secret: str = Field(min_length=1)
    item_id: str = Field(min_length=1)


class SetupRequest(BaseModel):
    nome: str = Field(min_length=1, max_length=255)
    email: str = Field(max_length=320)
    senha: str = Field(min_length=8, max_length=1024)
    # Obrigatório nesta rodada (decisão do produto): a instância já nasce conectada ao Pluggy.
    pluggy: PluggyCredenciais

    # Campos pessoais opcionais (#6). `salario_mensal` em REAIS → convertido para centavos (#2).
    data_nascimento: date | None = None
    salario_mensal: Decimal | None = Field(default=None, ge=0)
    formacao: str | None = Field(default=None, max_length=255)
    ocupacao: str | None = Field(default=None, max_length=255)

    _valida_email = field_validator("email")(_normalizar_email)

    @property
    def salario_mensal_centavos(self) -> int | None:
        if self.salario_mensal is None:
            return None
        return int((self.salario_mensal * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


class SetupStatus(BaseModel):
    configured: bool
    app_mode: str


class SetupIniciado(BaseModel):
    """Passo 1: material do TOTP p/ o QR + ticket cifrado (nada foi persistido ainda)."""

    totp_secret: str
    totp_provisioning_uri: str
    setup_ticket: str


class ConfirmarSetupRequest(BaseModel):
    setup_ticket: str = Field(min_length=1)
    codigo_totp: str = Field(min_length=6, max_length=8)
