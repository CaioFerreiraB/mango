"""Configuração, vínculo e polling. Um processo por instalação (mesmo limite do sync)."""

import logging
import secrets
import threading
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.exceptions import ConflictError, RateLimitError, UpstreamError
from app.models.configuracao import ConfiguracaoSistema
from app.models.telegram import ConfigTelegram, ExecucaoDiaria
from app.models.usuario import Usuario
from app.repositories.configuracao import ConfiguracaoSistemaRepository
from app.schemas.telegram import (
    IdentidadeTelegram,
    TelegramInstanciaRead,
    TelegramInstanciaUpdate,
    TelegramRead,
    VinculoRead,
)
from app.security.current_user import _aware, hash_token
from app.services.periodo import SP
from app.telegram_client import TelegramClient, TelegramError

logger = logging.getLogger("app.telegram")
# ponytail: lock por processo, como no sync. Ao escalar workers, isolar o consumidor/job.
# Serializa confirmação/desvinculação/envio; polling de rede e sync ficam fora do lock.
lock = threading.RLock()
_parar = threading.Event()
_thread: threading.Thread | None = None


def agora() -> datetime:
    return datetime.now(UTC)


def instancia(db: Session) -> ConfiguracaoSistema:
    return ConfiguracaoSistemaRepository(db).obter()


def config_usuario(db: Session, usuario_id: int) -> ConfigTelegram:
    config = db.scalar(select(ConfigTelegram).where(ConfigTelegram.usuario_id == usuario_id))
    if config is None:
        config = ConfigTelegram(usuario_id=usuario_id)
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


def ler_instancia(config: ConfiguracaoSistema) -> TelegramInstanciaRead:
    return TelegramInstanciaRead(
        configurado=bool(config.telegram_token_cifrado),
        bot_username=config.telegram_username,
        ativo=config.telegram_ativo,
        erro=config.telegram_erro,
    )


def ler(db: Session, usuario_id: int) -> TelegramRead:
    geral, config = instancia(db), config_usuario(db, usuario_id)
    momento = agora()
    valido = bool(
        config.solicitacao_id
        and config.vinculo_expira_em
        and _aware(config.vinculo_expira_em) > momento
    )
    identidade = (
        IdentidadeTelegram(
            usuario_id=config.telegram_usuario_id,
            nome=config.telegram_nome,
            username=config.telegram_username,
        )
        if config.ativo and config.telegram_usuario_id
        else None
    )
    candidato = (
        IdentidadeTelegram(
            usuario_id=config.candidato_id,
            nome=config.candidato_nome,
            username=config.candidato_username,
        )
        if valido and config.candidato_id
        else None
    )
    proxima = None
    ultima = db.scalar(
        select(ExecucaoDiaria)
        .where(ExecucaoDiaria.usuario_id == usuario_id)
        .order_by(ExecucaoDiaria.data.desc())
        .limit(1)
    )
    if geral.sync_automatico:
        hoje = momento.astimezone(SP).date()
        proxima = datetime.combine(hoje, geral.sync_horario, SP)
        execucao = db.scalar(
            select(ExecucaoDiaria).where(
                ExecucaoDiaria.usuario_id == usuario_id, ExecucaoDiaria.data == hoje
            )
        )
        if execucao and execucao.sync_status in {"concluido", "falhou"}:
            proxima += timedelta(days=1)
        elif execucao and execucao.proxima_tentativa:
            proxima = _aware(execucao.proxima_tentativa)
        elif proxima < momento:
            proxima = momento  # vencida: próxima passagem do verificador (até um minuto)
    return TelegramRead(
        configurado=bool(geral.telegram_token_cifrado),
        bot_username=geral.telegram_username,
        ativo=geral.telegram_ativo,
        vinculado=identidade is not None,
        identidade=identidade,
        candidato=candidato,
        solicitacao_id=config.solicitacao_id if valido else None,
        vinculo_expira_em=_aware(config.vinculo_expira_em) if valido else None,
        notif_nao_revisadas=config.notif_nao_revisadas,
        ultimo_envio_em=_aware(config.ultimo_envio_em) if config.ultimo_envio_em else None,
        erro=config.erro or geral.telegram_erro or (ultima.erro if ultima else None),
        sync_automatico=geral.sync_automatico,
        sync_horario=geral.sync_horario,
        proxima_rotina=proxima,
    )


def cancelar_pendentes(db: Session, usuario_id: int | None = None) -> None:
    stmt = update(ExecucaoDiaria).where(ExecucaoDiaria.envio_status == "pendente")
    if usuario_id is not None:
        stmt = stmt.where(ExecucaoDiaria.usuario_id == usuario_id)
    db.execute(stmt.values(envio_status="ignorado"))


def limpar_solicitacao(config: ConfigTelegram) -> None:
    for campo in (
        "vinculo_hash",
        "solicitacao_id",
        "vinculo_expira_em",
        "candidato_id",
        "candidato_nome",
        "candidato_username",
    ):
        setattr(config, campo, None)


def _desvincular(config: ConfigTelegram) -> None:
    config.chat_id = config.telegram_usuario_id = None
    config.telegram_nome = config.telegram_username = None
    config.ativo = config.notif_nao_revisadas = False
    config.erro = None
    limpar_solicitacao(config)


def atualizar_instancia(
    db: Session, payload: TelegramInstanciaUpdate, origem: str
) -> TelegramInstanciaRead:
    config = instancia(db)
    campos = payload.model_dump(exclude_unset=True)
    token = payload.token or config.telegram_token_cifrado
    validar = bool(payload.token or campos.get("ativo"))
    identidade = None
    if validar:
        if not token:
            raise ConflictError("configure o token do bot primeiro")
        try:
            with TelegramClient(token) as cliente:
                identidade = cliente.get_me()
                if cliente.webhook_info().get("url"):
                    raise ConflictError(
                        "este bot tem webhook ativo; use um bot exclusivo sem webhook"
                    )
        except TelegramError as exc:
            raise UpstreamError(f"não foi possível validar o bot ({exc.codigo})") from None
    if identidade:
        novo_id = str(identidade["id"])
        mudou = config.telegram_bot_id is not None and config.telegram_bot_id != novo_id
        if mudou and not payload.confirmar_troca_bot:
            raise ConflictError("outro bot: confirme a troca; todos precisarão vincular novamente")
        if mudou:
            for individual in db.scalars(select(ConfigTelegram)).all():
                _desvincular(individual)
            cancelar_pendentes(db)
            config.telegram_offset = 0
        config.telegram_bot_id, config.telegram_username = novo_id, identidade["username"]
        config.telegram_token_cifrado = token
        config.telegram_erro = None
    if "ativo" in campos:
        config.telegram_ativo = payload.ativo
    config.telegram_url = origem
    if not config.telegram_ativo:
        cancelar_pendentes(db)
    db.commit()
    return ler_instancia(config)


def remover_instancia(db: Session) -> None:
    config = instancia(db)
    config.telegram_token_cifrado = config.telegram_bot_id = config.telegram_username = None
    config.telegram_ativo, config.telegram_offset, config.telegram_erro = False, 0, None
    for individual in db.scalars(select(ConfigTelegram)).all():
        _desvincular(individual)
    cancelar_pendentes(db)
    db.commit()


def criar_vinculo(db: Session, usuario_id: int) -> VinculoRead:
    geral, config = instancia(db), config_usuario(db, usuario_id)
    if not geral.telegram_ativo or not geral.telegram_username:
        raise ConflictError("a integração Telegram está desativada")
    segredo = secrets.token_urlsafe(32)
    limpar_solicitacao(config)
    config.vinculo_hash, config.solicitacao_id = hash_token(segredo), secrets.token_urlsafe(16)
    config.vinculo_expira_em = agora() + timedelta(minutes=10)
    db.commit()
    return VinculoRead(
        solicitacao_id=config.solicitacao_id,
        url=f"https://t.me/{geral.telegram_username}?start={segredo}",
        expira_em=_aware(config.vinculo_expira_em),
    )


def processar_update(db: Session, evento: dict) -> None:
    """Entrada não confiável do Telegram; nenhuma identidade vem do cliente Mango."""
    mensagem = evento.get("message")
    if not isinstance(mensagem, dict):
        return
    chat, pessoa, texto = mensagem.get("chat"), mensagem.get("from"), mensagem.get("text")
    if not isinstance(chat, dict) or not isinstance(pessoa, dict) or not isinstance(texto, str):
        return
    identificador = pessoa.get("id")
    if (
        chat.get("type") != "private"
        or type(identificador) is not int
        or not 0 < identificador < 2**63
        or type(chat.get("id")) is not int
        or chat.get("id") != identificador
        or pessoa.get("is_bot")
    ):
        return
    comando, _, segredo = texto.partition(" ")
    if comando.split("@")[0] != "/start" or not segredo or len(segredo) > 64:
        return
    config = db.scalar(
        select(ConfigTelegram).where(ConfigTelegram.vinculo_hash == hash_token(segredo))
    )
    if (
        config is None
        or config.vinculo_expira_em is None
        or _aware(config.vinculo_expira_em) <= agora()
    ):
        return
    usuario = db.get(Usuario, config.usuario_id)
    if usuario is None or not usuario.ativo or usuario.tipo != "completo":
        return
    config.candidato_id = str(identificador)
    config.candidato_nome = " ".join(str(pessoa.get("first_name") or "").split())[:255]
    config.candidato_username = str(pessoa["username"])[:255] if pessoa.get("username") else None
    config.vinculo_hash = None  # consumo antes de expor candidato; replay não o substitui
    db.commit()


def confirmar_vinculo(db: Session, usuario_id: int, solicitacao_id: str) -> TelegramRead:
    config = config_usuario(db, usuario_id)
    if (
        not instancia(db).telegram_ativo
        or config.solicitacao_id != solicitacao_id
        or not config.candidato_id
        or not config.vinculo_expira_em
        or _aware(config.vinculo_expira_em) <= agora()
    ):
        raise ConflictError("solicitação inválida ou expirada; inicie a vinculação novamente")
    config.telegram_usuario_id = config.chat_id = config.candidato_id
    config.telegram_nome, config.telegram_username = (
        config.candidato_nome,
        config.candidato_username,
    )
    config.ativo, config.notif_nao_revisadas, config.erro = True, False, None
    limpar_solicitacao(config)
    cancelar_pendentes(db, usuario_id)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError("esta identidade Telegram já está vinculada") from None
    return ler(db, usuario_id)


def desvincular(db: Session, usuario_id: int) -> None:
    _desvincular(config_usuario(db, usuario_id))
    cancelar_pendentes(db, usuario_id)
    db.commit()


def preferencia(db: Session, usuario_id: int, habilitar: bool) -> TelegramRead:
    config = config_usuario(db, usuario_id)
    if habilitar and not (config.ativo and config.telegram_usuario_id):
        raise ConflictError("vincule seu Telegram primeiro")
    config.notif_nao_revisadas = habilitar
    if habilitar:
        config.erro = None
    else:
        cancelar_pendentes(db, usuario_id)
    db.commit()
    return ler(db, usuario_id)


def registrar_erro(
    db: Session, geral: ConfiguracaoSistema, config: ConfigTelegram | None, exc: TelegramError
) -> None:
    if exc.codigo == "token_invalido":
        geral.telegram_ativo, geral.telegram_erro = False, exc.codigo
    elif config is not None:
        config.erro = exc.codigo
        if exc.codigo == "destinatario_bloqueou":
            config.notif_nao_revisadas = False
    else:
        geral.telegram_erro = exc.codigo
    db.commit()


def testar(db: Session, usuario_id: int) -> None:
    config, geral = config_usuario(db, usuario_id), instancia(db)
    if not geral.telegram_ativo or not config.ativo or not config.chat_id:
        raise ConflictError("ative a integração e confirme seu vínculo primeiro")
    momento = agora()
    if config.ultimo_teste_em and momento - _aware(config.ultimo_teste_em) < timedelta(minutes=1):
        raise RateLimitError("aguarde um minuto antes de testar novamente")
    config.ultimo_teste_em = momento
    db.commit()
    try:
        with TelegramClient(geral.telegram_token_cifrado) as cliente:
            cliente.send_message(
                config.chat_id,
                "Mango conectado. Esta é uma mensagem de teste, sem dados financeiros.",
            )
    except TelegramError as exc:
        registrar_erro(db, geral, config, exc)
        raise UpstreamError(f"não foi possível confirmar o teste ({exc.codigo})") from None
    config.erro = None
    db.commit()


def _polling() -> None:
    while not _parar.is_set():
        espera = 2
        try:
            with SessionLocal() as db:
                with lock:
                    config = instancia(db)
                    token = config.telegram_token_cifrado if config.telegram_ativo else None
                    offset = config.telegram_offset
                if token:
                    with TelegramClient(token) as cliente:
                        eventos = cliente.updates(offset)
                    with lock:
                        db.expire_all()
                        config = instancia(db)
                        if config.telegram_token_cifrado != token or not config.telegram_ativo:
                            continue
                        for evento in eventos:
                            if (
                                not isinstance(evento, dict)
                                or type(evento.get("update_id")) is not int
                                or not 0 <= evento["update_id"] < 2**63 - 1
                            ):
                                continue
                            if evento["update_id"] < config.telegram_offset:
                                continue
                            processar_update(db, evento)
                            config.telegram_offset = evento["update_id"] + 1
                            db.commit()
                        if config.telegram_erro:
                            config.telegram_erro = None
                            db.commit()
        except TelegramError as exc:
            espera = max(5, exc.espera)
            with lock, SessionLocal() as db:
                config = instancia(db)
                if config.telegram_token_cifrado == token:
                    registrar_erro(db, config, None, exc)
        except Exception:
            # Não logar traceback: exceções de transporte podem carregar a URL com token.
            logger.error("polling Telegram indisponível")
            espera = 30
        _parar.wait(espera)


def iniciar() -> None:
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    _parar.clear()
    _thread = threading.Thread(target=_polling, name="mango-telegram", daemon=True)
    _thread.start()


def parar() -> None:
    global _thread
    _parar.set()
    if _thread is not None:
        _thread.join(timeout=40)
        _thread = None
