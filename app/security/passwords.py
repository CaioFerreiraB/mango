"""Hashing de senhas (§5.2): bcrypt, nunca texto plano.

bcrypt trunca em 72 bytes; pré-hasheamos com SHA-256 (hex, 64 bytes) para aceitar senhas longas
sem perder entropia — padrão recomendado ao usar bcrypt direto.
"""

import hashlib

import bcrypt


def _preparar(senha: str) -> bytes:
    return hashlib.sha256(senha.encode("utf-8")).hexdigest().encode("ascii")


def hash_password(senha: str) -> str:
    return bcrypt.hashpw(_preparar(senha), bcrypt.gensalt()).decode("ascii")


def verify_password(senha: str, senha_hash: str) -> bool:
    if not senha_hash:
        return False
    return bcrypt.checkpw(_preparar(senha), senha_hash.encode("ascii"))
