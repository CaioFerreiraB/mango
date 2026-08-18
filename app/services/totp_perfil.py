"""2FA do usuário já logado (§5.2, #15): cadastrar, trocar e habilitar/desabilitar no login.

Mesmo desenho de ticket cifrado de 2 passos do `app/services/setup.py`/`app/services/convite.py`
(passo 1 gera o segredo e sela um ticket, nada persiste; passo 2 só grava se o código bater) —
"trocar" é só cadastrar de novo, o secret anterior é substituído inteiro. Reconfirmar a senha atual
(step-up) fica a cargo do router, mesmo padrão do `_CREDENCIAL_INVALIDA` de `app/routers/auth.py`
— serviços não levantam `HTTPException` (só erros de domínio, ver `app/exceptions.py`).
"""

import json

from sqlalchemy.orm import Session

from app.exceptions import ValidationError
from app.models.usuario import Usuario
from app.schemas.perfil import TotpIniciado
from app.security import encryption, totp

_TICKET_TTL = 900  # 15 min entre exibir o QR e confirmar o código (mesmo TTL do setup/convite)


def iniciar_troca(user: Usuario) -> TotpIniciado:
    """Passo 1: gera um novo segredo e sela o ticket — nada é gravado ainda."""
    secret = totp.gerar_secret()
    ticket = encryption.encrypt(json.dumps({"usuario_id": user.id, "totp_secret": secret}))
    return TotpIniciado(
        totp_secret=secret,
        totp_provisioning_uri=totp.provisioning_uri(secret, user.email),
        ticket=ticket,
    )


def confirmar_troca(db: Session, user: Usuario, ticket: str, codigo_totp: str) -> Usuario:
    """Passo 2: valida o código do NOVO segredo e só então grava (troca de fato)."""
    bruto = encryption.unseal(ticket, ttl=_TICKET_TTL)
    if bruto is None:
        raise ValidationError("ticket inválido ou expirado; comece de novo")
    dados = json.loads(bruto)
    if dados["usuario_id"] != user.id:
        raise ValidationError("ticket não pertence a este usuário")
    if not totp.verificar(dados["totp_secret"], codigo_totp):
        raise ValidationError("código incorreto")

    alvo = db.get(Usuario, user.id)
    alvo.totp_secret_cifrado = dados["totp_secret"]  # EncryptedStr cifra em repouso (§5.5)
    alvo.totp_login_habilitado = True  # cadastrar/trocar já liga a exigência no login
    db.commit()
    db.refresh(alvo)
    return alvo


def habilitar_login(db: Session, user: Usuario) -> None:
    if not user.totp_configurado:
        raise ValidationError("configure o 2FA antes de exigi-lo no login")
    alvo = db.get(Usuario, user.id)
    alvo.totp_login_habilitado = True
    db.commit()


def desabilitar_login(db: Session, user: Usuario) -> None:
    alvo = db.get(Usuario, user.id)
    alvo.totp_login_habilitado = False
    db.commit()
