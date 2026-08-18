"""Schemas de autenticação (§5.2, #15): login com 2FA e recuperação de senha via TOTP."""

from pydantic import BaseModel, Field, field_validator

from app.schemas.setup import _normalizar_email
from app.schemas.usuario import TipoUsuario


class LoginRequest(BaseModel):
    email: str
    senha: str
    # Opcional (§5.2, #15): só é exigido quando `usuario.totp_exigido_no_login` for True — ver
    # `LoginResponse.totp_necessario`, que sinaliza isso ao cliente após validar a senha.
    codigo_totp: str | None = Field(default=None, min_length=6, max_length=8)

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
    tipo: TipoUsuario
    is_admin: bool
    totp_configurado: bool
    totp_login_habilitado: bool


class LoginResponse(BaseModel):
    """`usuario` vem preenchido quando o login conclui (sessão criada). `totp_necessario=True`
    e `usuario=None` quando a senha bateu mas falta o código — SEM sessão/cookie criados; o
    cliente deve reenviar o mesmo request com `codigo_totp` preenchido."""

    totp_necessario: bool = False
    usuario: MeRead | None = None
