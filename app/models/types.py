"""Tipos SQLAlchemy reutilizáveis."""

from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

from app.security import encryption


class EncryptedStr(TypeDecorator):
    """Coluna de texto cifrada em repouso (Fernet) — usada nas colunas `*_cifrado` (§5.5).

    Cifra ao gravar e decifra ao ler, de forma transparente. Persistido como TEXT
    (o token é maior que o texto puro). Não indexável por igualdade.
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect) -> str | None:  # noqa: ANN001
        if value is None:
            return None
        return encryption.encrypt(value)

    def process_result_value(self, value: str | None, dialect) -> str | None:  # noqa: ANN001
        if value is None:
            return None
        return encryption.decrypt(value)
