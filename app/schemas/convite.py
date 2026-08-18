"""Schemas do convite de pessoa "só divisão" (§4.11, §3) — mesmo shape em 2 passos do setup
(app/schemas/setup.py): gera o TOTP e um ticket cifrado; só persiste após confirmar o código.
"""

from pydantic import BaseModel, Field, field_validator

from app.schemas.setup import _normalizar_email
from app.schemas.usuario import TipoUsuario


class ConvidarPessoaRequest(BaseModel):
    nome: str = Field(min_length=1, max_length=255)
    email: str = Field(max_length=320)
    tipo: TipoUsuario = "completo"

    _valida_email = field_validator("email")(_normalizar_email)


class ConvidarPessoaRead(BaseModel):
    usuario_id: int
    link_convite: str


class ConviteStatus(BaseModel):
    nome: str
    expirado: bool
    usado: bool


class IniciarConviteRequest(BaseModel):
    senha: str = Field(min_length=8, max_length=1024)
    # 2FA é opcional (§5.2, #15) — default True preserva o comportamento atual quando omitido.
    ativar_totp: bool = True


class IniciarConviteResponse(BaseModel):
    """Passo 1: material do TOTP p/ o QR + ticket cifrado (senha + segredo, nada persistido).

    Campos de TOTP vêm `None` quando `ativar_totp=False` — o passo 2 conclui sem pedir código.
    """

    totp_secret: str | None
    totp_provisioning_uri: str | None
    ticket: str


class ConfirmarConviteRequest(BaseModel):
    ticket: str = Field(min_length=1)
    codigo_totp: str | None = Field(default=None, min_length=6, max_length=8)
