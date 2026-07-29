"""CLI administrativa do dono da instância (#15, backstop).

Uso no container:  docker compose exec app python -m app.cli reset-password <email> [--reset-totp]

Cobre a perda do dispositivo autenticador: reseta a senha e, opcionalmente, regenera o TOTP
(imprimindo o novo segredo/URI para reconfigurar o app). Invalida todas as sessões.
"""

import argparse
import sys
from getpass import getpass

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.usuario import Usuario
from app.security import passwords, totp
from app.security.sessions import revogar_todas


def _reset_password(email: str, reset_totp: bool) -> int:
    with SessionLocal() as db:
        usuario = db.scalars(select(Usuario).where(Usuario.email == email.strip().lower())).first()
        if usuario is None:
            print(f"usuário não encontrado: {email}", file=sys.stderr)
            return 1

        nova = getpass("Nova senha: ")
        if len(nova) < 8:
            print("senha muito curta (mínimo 8)", file=sys.stderr)
            return 1
        if nova != getpass("Confirme a nova senha: "):
            print("as senhas não conferem", file=sys.stderr)
            return 1

        usuario.senha_hash = passwords.hash_password(nova)
        if reset_totp:
            secret = totp.gerar_secret()
            usuario.totp_secret_cifrado = secret
        db.commit()
        revogar_todas(db, usuario.id)

        print(f"senha redefinida para {usuario.email}; todas as sessões foram encerradas.")
        if reset_totp:
            print("Novo TOTP — reconfigure seu app autenticador:")
            print(f"  segredo: {secret}")
            print(f"  uri:     {totp.provisioning_uri(secret, usuario.email)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)

    rp = sub.add_parser("reset-password", help="redefine a senha (e opcionalmente o TOTP)")
    rp.add_argument("email")
    rp.add_argument("--reset-totp", action="store_true", help="também regenera o segredo TOTP")

    args = parser.parse_args(argv)
    if args.cmd == "reset-password":
        return _reset_password(args.email, args.reset_totp)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
