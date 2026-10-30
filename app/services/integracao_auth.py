"""Identidade de integração nunca vem de argumento de ferramenta ou de initDataUnsafe."""

import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qsl

from fastapi import HTTPException, Request
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models.integracao import ConfigIntegracao, CredencialIntegracao, TrabalhoTelegram
from app.models.telegram import ConfigTelegram
from app.models.usuario import Usuario
from app.security.current_user import _aware, hash_token
from app.services.telegram import instancia


def configuracao(db: Session) -> ConfigIntegracao:
    obj = db.get(ConfigIntegracao, 1)
    if obj is None:
        obj = ConfigIntegracao(id=1)
        db.add(obj)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            obj = db.get(ConfigIntegracao, 1)
            if obj is None:
                raise
    return obj


def validar_init_data(raw: str, token: str) -> str:
    try:
        pares = parse_qsl(raw, strict_parsing=True, max_num_fields=32)
        dados = dict(pares)
        if len(dados) != len(pares) or len(raw) > 16384:
            raise ValueError
        assinatura = dados.pop("hash")
        segredo = hmac.digest(b"WebAppData", token.encode(), "sha256")
        esperado = hmac.new(
            segredo,
            "\n".join(f"{k}={v}" for k, v in sorted(dados.items())).encode(),
            hashlib.sha256,
        ).hexdigest()
        idade = datetime.now(UTC).timestamp() - int(dados["auth_date"])
        pessoa = json.loads(dados["user"])
        identificador = pessoa["id"]
        if (
            not hmac.compare_digest(esperado, assinatura)
            or not -30 <= idade <= 300
            or type(identificador) is not int
            or not 0 < identificador < 2**63
            or pessoa.get("is_bot")
        ):
            raise ValueError
        return str(identificador)
    except (ValueError, KeyError, TypeError):
        raise HTTPException(401, "autenticação Telegram inválida ou expirada") from None


def emitir(db: Session, usuario_id: int, tipo: str, trabalho_id: int | None = None) -> str:
    geral = instancia(db)
    vinculo = db.scalar(select(ConfigTelegram).where(ConfigTelegram.usuario_id == usuario_id))
    if not geral.telegram_ativo or not vinculo or not vinculo.ativo:
        raise HTTPException(401, "vínculo Telegram indisponível")
    token = "mgi_" + secrets.token_urlsafe(32)
    db.add(
        CredencialIntegracao(
            token_hash=hash_token(token),
            usuario_id=usuario_id,
            tipo=tipo,
            escopo=db.get(Usuario, usuario_id).tipo,
            bot_id=geral.telegram_bot_id,
            telegram_id=vinculo.telegram_usuario_id,
            trabalho_id=trabalho_id,
            expira_em=datetime.now(UTC) + timedelta(minutes=60 if tipo == "miniapp" else 5),
        )
    )
    db.commit()
    return token


def resolver(db: Session, token: str) -> tuple[Usuario, CredencialIntegracao]:
    cred = db.get(CredencialIntegracao, hash_token(token), populate_existing=True)
    if not cred or cred.revogada or _aware(cred.expira_em) <= datetime.now(UTC):
        raise HTTPException(401, "credencial de integração inválida ou expirada")
    geral = instancia(db)
    vinculo = db.scalar(select(ConfigTelegram).where(ConfigTelegram.usuario_id == cred.usuario_id))
    usuario = db.get(Usuario, cred.usuario_id)
    if (
        not usuario
        or not usuario.ativo
        or usuario.tipo != cred.escopo
        or not geral.telegram_ativo
        or geral.telegram_bot_id != cred.bot_id
        or not vinculo
        or not vinculo.ativo
        or vinculo.telegram_usuario_id != cred.telegram_id
    ):
        raise HTTPException(401, "integração revogada")
    if cred.tipo == "miniapp":
        if settings.app_mode != "self_hosted" or not configuracao(db).miniapp_ativo:
            raise HTTPException(401, "miniapp desativado")
    else:
        trabalho = db.get(TrabalhoTelegram, cred.trabalho_id, populate_existing=True)
        if (
            not trabalho
            or trabalho.status != "executando"
            or trabalho.usuario_id != cred.usuario_id
            or trabalho.bot_id != cred.bot_id
            or trabalho.chat_id != vinculo.chat_id
        ):
            raise HTTPException(401, "execução encerrada")
    return usuario, cred


def revogar(db: Session, usuario_id: int | None = None, trabalho_id: int | None = None) -> None:
    stmt = update(CredencialIntegracao)
    if usuario_id is not None:
        stmt = stmt.where(CredencialIntegracao.usuario_id == usuario_id)
    if trabalho_id is not None:
        stmt = stmt.where(CredencialIntegracao.trabalho_id == trabalho_id)
    db.execute(stmt.values(revogada=True))
    db.commit()


def autorizar_rota(request: Request, cred: CredencialIntegracao, usuario: Usuario) -> None:
    from app.security.current_user import _ROTAS_TOKEN

    caminho, metodo = request.url.path, request.method
    if cred.tipo == "delegada" and metodo != "GET" and request.scope.get("mango_db") is None:
        raise HTTPException(403, "escritas de IA passam pela política de ferramentas")
    rotas = dict(_ROTAS_TOKEN)
    if cred.tipo == "miniapp":
        rotas = {
            p: {"GET"}
            for p in (
                "/api/perfil",
                "/api/auth/me",
                "/api/transacoes",
                "/api/assinaturas",
                "/api/contas",
                "/api/categorias",
                "/api/usuarios/buscar",
                "/api/configuracao-sistema",
            )
        }
        rotas.update(
            {
                "/api/revisao": {"GET", "POST"},
                "/api/divisoes-despesa": {"GET", "POST", "PATCH", "DELETE"},
            }
        )
        # Regras e assinaturas novas são criadas no salvamento atômico da revisão.
        rotas["/api/assinaturas"] = {"GET"}
        rotas["/api/transacoes"] = {"GET"}
    if usuario.tipo == "divisao":
        rotas = {
            p: v
            for p, v in rotas.items()
            if p
            in {
                "/api/divisoes-despesa",
                "/api/usuarios/buscar",
                "/api/auth/me",
                "/api/configuracao-sistema",
                "/api/categorias",
            }
        }
    permitidos = next(
        (v for p, v in rotas.items() if caminho == p or caminho.startswith(p + "/")), ()
    )
    if metodo not in permitidos:
        raise HTTPException(403, "recurso fora do alcance da integração")
