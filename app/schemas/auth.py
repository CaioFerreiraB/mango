"""Schemas de autenticação (§5.2, #15): login com 2FA e recuperação de senha via TOTP."""

from pydantic import BaseModel, Field, field_validator

from app.schemas.setup import _normalizar_email


class LoginRequest(BaseModel):
    email: str
    senha: str
    codigo_totp: str = Field(min_length=6, max_length=8)

    _valida_email = field_validator("email")(_normalizar_email)


class RecuperarSenhaRequest(BaseModel):
    email: str
    codigo_totp: str = Field(min_length=6, max_length=8)
    nova_senha: str = Field(min_length=8, max_length=1024)

    _valida_email = field_validator("email")(_normalizar_email)


class MeRead(BaseModel):
    id: int
    nome: str
    email: str
    accent: str | None = None
    avatar: int | None = None
