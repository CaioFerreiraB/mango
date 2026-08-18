"""Convite de pessoa "só divisão" (§4.11, §3) — mesmo desenho de 2 passos do first-run setup
(`app/services/setup.py`): o passo 1 gera o TOTP e sela um ticket cifrado (nada persistido); o
passo 2 só grava se o código do autenticador bater. Sem e-mail (decisão #15): o link é copiado e
enviado manualmente pelo convidante.
"""

import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import Request
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.convite import ConviteUsuario
from app.models.usuario import Sessao, Usuario
from app.schemas.convite import ConviteStatus, IniciarConviteResponse
from app.security import encryption, passwords, totp
from app.security.sessions import nova_sessao

_EXPIRACAO_CONVITE = timedelta(days=7)
_TICKET_TTL = 900  # 15 min entre exibir o QR e confirmar o código (mesmo TTL do setup)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _expirado(convite: ConviteUsuario) -> bool:
    expira_em = convite.expira_em
    if expira_em.tzinfo is None:  # SQLite devolve naive — assume UTC (mesmo ajuste do current_user)
        expira_em = expira_em.replace(tzinfo=UTC)
    return expira_em < datetime.now(UTC)


def _por_token(db: Session, token: str) -> ConviteUsuario | None:
    return db.scalars(
        select(ConviteUsuario).where(ConviteUsuario.token_hash == _hash_token(token))
    ).first()


def _criar_convite(db: Session, criado_por: Usuario, usuario: Usuario) -> str:
    """Gera o token cru + grava o `ConviteUsuario` (não commita — quem chama decide). O token só
    existe em claro aqui, nunca mais é recuperável."""
    token = secrets.token_urlsafe(32)
    agora = datetime.now(UTC)
    db.add(
        ConviteUsuario(
            usuario_id=usuario.id,
            criado_por_usuario_id=criado_por.id,
            token_hash=_hash_token(token),
            criado_em=agora,
            expira_em=agora + _EXPIRACAO_CONVITE,
        )
    )
    return token


def convidar(
    db: Session, criado_por: Usuario, nome: str, email: str, tipo: str = "completo"
) -> tuple[Usuario, str]:
    """Cria o usuário placeholder (`senha_hash` nulo = "só divisão", eixo independente de `tipo`)
    + o convite. Devolve (usuário, token cru)."""
    if db.scalars(select(Usuario).where(Usuario.email == email)).first() is not None:
        raise ConflictError("já existe uma conta com este e-mail nesta instância")

    usuario = Usuario(nome=nome, email=email, tipo=tipo)  # senha_hash nulo até aceitar o convite
    db.add(usuario)
    db.flush()

    token = _criar_convite(db, criado_por, usuario)
    db.commit()
    db.refresh(usuario)
    return usuario, token


def reenviar(db: Session, admin: Usuario, usuario_id: int) -> tuple[Usuario, str]:
    """Invalida qualquer convite pendente do usuário e gera um novo link (7 dias) — o link
    anterior deixa de funcionar. Só faz sentido para quem ainda não ativou a conta."""
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise NotFoundError("usuário não encontrado")
    if usuario.senha_hash is not None:
        raise ConflictError("usuário já ativou a conta; não há convite pendente para reenviar")

    db.execute(
        delete(ConviteUsuario).where(
            ConviteUsuario.usuario_id == usuario_id, ConviteUsuario.usado_em.is_(None)
        )
    )
    token = _criar_convite(db, admin, usuario)
    db.commit()
    db.refresh(usuario)
    return usuario, token


def status(db: Session, token: str) -> ConviteStatus:
    convite = _por_token(db, token)
    if convite is None:
        raise NotFoundError("convite não encontrado")
    usuario = db.get(Usuario, convite.usuario_id)
    return ConviteStatus(
        nome=usuario.nome,
        expirado=_expirado(convite),
        usado=convite.usado_em is not None,
    )


def iniciar(
    db: Session, token: str, senha: str, ativar_totp: bool = True
) -> IniciarConviteResponse:
    """Passo 1: valida o convite, gera o TOTP (se pedido) e sela o ticket — nada é gravado ainda."""
    convite = _por_token(db, token)
    if convite is None:
        raise NotFoundError("convite não encontrado")
    if convite.usado_em is not None:
        raise ConflictError("convite já foi utilizado")
    if _expirado(convite):
        raise ValidationError("convite expirado; peça um novo link")

    usuario = db.get(Usuario, convite.usuario_id)
    totp_secret = totp.gerar_secret() if ativar_totp else None
    ticket = encryption.encrypt(
        json.dumps(
            {
                "convite_id": convite.id,
                "usuario_id": usuario.id,
                "senha": senha,
                "totp_secret": totp_secret,
            }
        )
    )
    return IniciarConviteResponse(
        totp_secret=totp_secret,
        totp_provisioning_uri=(
            totp.provisioning_uri(totp_secret, usuario.email) if totp_secret else None
        ),
        ticket=ticket,
    )


def confirmar(
    db: Session, ticket: str, codigo_totp: str | None, request: Request | None = None
) -> tuple[Usuario, Sessao]:
    """Passo 2: valida o código (quando há segredo no ticket) e só então grava senha + TOTP no
    usuário placeholder e loga."""
    bruto = encryption.unseal(ticket, ttl=_TICKET_TTL)
    if bruto is None:
        raise ValidationError("ticket de convite inválido ou expirado; recomece o cadastro")
    dados = json.loads(bruto)

    totp_secret = dados["totp_secret"]
    if totp_secret is not None:
        if not totp.verificar(totp_secret, codigo_totp or ""):
            raise ValidationError("código incorreto")

    convite = db.get(ConviteUsuario, dados["convite_id"])
    if convite is None or convite.usado_em is not None:
        raise ConflictError("convite já foi utilizado")
    if _expirado(convite):
        raise ValidationError("convite expirado; peça um novo link")

    usuario = db.get(Usuario, dados["usuario_id"])
    if usuario is None:
        raise NotFoundError("usuário do convite não encontrado")

    usuario.senha_hash = passwords.hash_password(dados["senha"])
    usuario.totp_secret_cifrado = totp_secret  # EncryptedStr cifra em repouso (§5.5); None se pulou
    usuario.totp_login_habilitado = totp_secret is not None
    convite.usado_em = datetime.now(UTC)

    sessao = nova_sessao(usuario.id, request)
    db.add(sessao)

    db.commit()
    db.refresh(usuario)
    db.refresh(sessao)
    return usuario, sessao
