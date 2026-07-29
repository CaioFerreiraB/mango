"""TOTP (§5.2, #15): 2FA no login e base da recuperação de senha sem e-mail.

O segredo é gerado no cadastro, exibido como QR (o frontend renderiza a partir do
`provisioning_uri`) e guardado cifrado em repouso (`usuario.totp_secret_cifrado`, EncryptedStr).
"""

import pyotp

_ISSUER = "mango"


def gerar_secret() -> str:
    return pyotp.random_base32()


def provisioning_uri(secret: str, email: str) -> str:
    """URI `otpauth://` para o app autenticador (vira QR no frontend)."""
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=_ISSUER)


def verificar(secret: str, codigo: str) -> bool:
    if not secret or not codigo:
        return False
    # valid_window=1 tolera ±30s de defasagem de relógio entre servidor e app.
    return pyotp.TOTP(secret).verify(codigo.strip(), valid_window=1)
