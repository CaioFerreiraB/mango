"""Configuração administrativa e bootstrap do Mini App, independentes da sessão web."""

from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.exceptions import ValidationError
from app.models.integracao import CredencialIntegracao, PreferenciaIa
from app.models.telegram import ConfigTelegram
from app.models.usuario import Usuario
from app.schemas.integracao import (
    ConfigIaRead,
    ConfigIaUpdate,
    MiniappConfig,
    MiniappLogin,
    MiniappSessao,
    PreferenciaIaRead,
    PreferenciaIaUpdate,
)
from app.security.current_user import exigir_usuario_completo, require_admin_ou_local
from app.services import integracao_auth as auth
from app.services import provedor_ia
from app.services.telegram import instancia
from app.telegram_client import TelegramClient, TelegramError

router = APIRouter(tags=["integracao"])


def leitura(c) -> ConfigIaRead:
    return ConfigIaRead(
        ativa=c.ia_ativa,
        provedor=c.provedor,
        endpoint=c.endpoint,
        modelo=c.modelo,
        configurada=bool(c.chave),
        validada=c.validado,
        limite_usuario=c.limite_usuario,
        limite_instancia=c.limite_instancia,
    )


@router.get("/ia/instancia", response_model=ConfigIaRead)
def obter(db: Session = Depends(get_db), user: Usuario = Depends(require_admin_ou_local)):
    return leitura(auth.configuracao(db))


@router.put("/ia/instancia", response_model=ConfigIaRead)
def salvar(
    payload: ConfigIaUpdate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_admin_ou_local),
):
    c = auth.configuracao(db)
    endpoint = provedor_ia.validar_endpoint(payload.provedor.endpoint)
    if payload.provedor.tipo == "axon" and settings.app_mode != "self_hosted":
        raise ValidationError("Axon está disponível apenas no self-hosted")
    if payload.provedor.tipo == "axon" and not urlsplit(endpoint).path.endswith("/private/v1"):
        raise ValidationError("o endpoint Axon deve incluir /private/v1")
    modelo = getattr(payload.provedor, "modelo", None)
    mudou = (
        c.endpoint != endpoint
        or c.provedor != payload.provedor.tipo
        or payload.provedor.chave is not None
        or (payload.provedor.tipo != "axon" and c.modelo != modelo)
    )
    if mudou:
        c.validado = False
        # Consentimento vale para a conexão apresentada ao usuário, não para um novo destino.
        db.execute(update(PreferenciaIa).values(ativa=False))
        db.execute(
            update(CredencialIntegracao)
            .where(CredencialIntegracao.tipo == "delegada")
            .values(revogada=True)
        )
        if c.endpoint != endpoint or c.provedor != payload.provedor.tipo:
            c.chave = None
        c.modelo = modelo
    c.provedor, c.endpoint = payload.provedor.tipo, endpoint
    if payload.provedor.chave:
        c.chave = payload.provedor.chave
    if payload.ativa and not c.validado:
        raise ValidationError("salve e teste a conexão antes de ativar")
    c.ia_ativa = payload.ativa
    c.limite_usuario, c.limite_instancia = payload.limite_usuario, payload.limite_instancia
    db.commit()
    if not c.ia_ativa:
        # Sessões do miniapp permanecem válidas: revogação aqui só atinge execuções de IA.
        db.execute(
            update(CredencialIntegracao)
            .where(CredencialIntegracao.tipo == "delegada")
            .values(revogada=True)
        )
        db.commit()
    return leitura(c)


@router.post("/ia/instancia/testar", response_model=ConfigIaRead)
async def testar(db: Session = Depends(get_db), user: Usuario = Depends(require_admin_ou_local)):
    c = auth.configuracao(db)
    c.validado = False
    db.commit()
    c.modelo = await provedor_ia.testar(c)
    c.validado = True
    db.commit()
    return leitura(c)


@router.get("/ia/preferencias", response_model=PreferenciaIaRead)
def preferencia(db: Session = Depends(get_db), user: Usuario = Depends(exigir_usuario_completo)):
    c = auth.configuracao(db)
    p = db.scalar(select(PreferenciaIa).where(PreferenciaIa.usuario_id == user.id))
    return PreferenciaIaRead(ativa=bool(p and p.ativa), disponivel=c.ia_ativa, provedor=c.provedor)


@router.put("/ia/preferencias", response_model=PreferenciaIaRead)
def atualizar_preferencia(
    payload: PreferenciaIaUpdate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(exigir_usuario_completo),
):
    p = db.scalar(select(PreferenciaIa).where(PreferenciaIa.usuario_id == user.id))
    if p is None:
        p = PreferenciaIa(usuario_id=user.id)
        db.add(p)
    p.ativa = payload.ativa
    db.commit()
    if not p.ativa:
        db.execute(
            update(CredencialIntegracao)
            .where(
                CredencialIntegracao.usuario_id == user.id, CredencialIntegracao.tipo == "delegada"
            )
            .values(revogada=True)
        )
        db.commit()
    return preferencia(db, user)


@router.get("/telegram/miniapp/config", response_model=MiniappConfig)
def miniapp_config(db: Session = Depends(get_db), user: Usuario = Depends(require_admin_ou_local)):
    c = auth.configuracao(db)
    return MiniappConfig(ativo=c.miniapp_ativo, url=c.url)


@router.put("/telegram/miniapp/config", response_model=MiniappConfig)
def miniapp_salvar(
    payload: MiniappConfig,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_admin_ou_local),
):
    if settings.app_mode != "self_hosted":
        raise ValidationError("miniapp está disponível apenas no self-hosted")
    try:
        url = urlsplit(payload.url or "")
        _ = url.port
    except ValueError:
        raise ValidationError("endereço do miniapp inválido") from None
    if (
        url.scheme != "https"
        or not url.hostname
        or url.username
        or url.password
        or url.query
        or url.fragment
        or url.path not in {"", "/"}
    ):
        raise ValidationError("informe a origem HTTPS do Mango, sem caminho ou credenciais")
    c = auth.configuracao(db)
    origem = payload.url.rstrip("/")
    if c.url != origem:
        c.validado, c.ia_ativa = False, False
        auth.revogar(db)
    geral = instancia(db)
    if payload.ativo and not geral.telegram_token_cifrado:
        raise ValidationError("configure o bot primeiro")
    if geral.telegram_token_cifrado:
        try:
            with TelegramClient(geral.telegram_token_cifrado) as client:
                client.menu(origem + "/telegram" if payload.ativo else None)
        except TelegramError:
            raise ValidationError(
                "não foi possível configurar o menu do bot; tente novamente"
            ) from None
    c.url, c.miniapp_ativo = origem, payload.ativo
    db.commit()
    if not payload.ativo:
        auth.revogar(db)
    return payload


@router.post("/telegram/miniapp/sessao", response_model=MiniappSessao)
def login(payload: MiniappLogin, db: Session = Depends(get_db)):
    c, geral = auth.configuracao(db), instancia(db)
    if settings.app_mode != "self_hosted" or not c.miniapp_ativo or not geral.telegram_ativo:
        raise HTTPException(404, "miniapp indisponível")
    identidade = auth.validar_init_data(payload.init_data, geral.telegram_token_cifrado or "")
    vinculo = db.scalar(
        select(ConfigTelegram).where(
            ConfigTelegram.telegram_usuario_id == identidade, ConfigTelegram.ativo.is_(True)
        )
    )
    if vinculo is None:
        raise HTTPException(401, "vincule e confirme seu Telegram no Mango primeiro")
    user = db.get(Usuario, vinculo.usuario_id)
    if not user or not user.ativo:
        raise HTTPException(401, "conta indisponível")
    token = auth.emitir(db, user.id, "miniapp")
    return MiniappSessao(
        token=token, expira_em=(datetime.now(UTC) + timedelta(hours=1)).isoformat()
    )
