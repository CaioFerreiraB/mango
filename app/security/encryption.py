"""Cifragem em repouso de segredos por usuário (§5.5, decisão #10).

Fernet (AES-128-CBC + HMAC). A chave vem do ambiente (`ENCRYPTION_KEY`); nunca embutida
na imagem em produção. Os tokens são não-determinísticos — não usar colunas cifradas em
buscas por igualdade (as chaves de upsert do Pluggy são campos em claro: `pluggy_*_id`).
"""

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    return Fernet(settings.encryption_key.encode())


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()


def unseal(token: str, ttl: int) -> str | None:
    """Decifra um token com validade (`ttl` em segundos); `None` se inválido/expirado.

    Usado no ticket efêmero do setup (dados round-trip no cliente, cifrados com a chave do
    servidor → opacos p/ o cliente), diferente de `decrypt` (colunas em repouso, sem expiração).
    """
    try:
        return _fernet().decrypt(token.encode(), ttl=ttl).decode()
    except InvalidToken:
        return None
