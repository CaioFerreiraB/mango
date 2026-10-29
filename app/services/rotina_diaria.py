"""Sync diário seguido de relatório; controle durável, sem fila/serviço externo."""

import logging
import threading
from datetime import datetime, timedelta

from sqlalchemy import select

from app.config import settings
from app.db.session import SessionLocal
from app.exceptions import ConflictError, RateLimitError
from app.models.pluggy import CredencialPluggy, ItemPluggy
from app.models.telegram import ConfigTelegram, ExecucaoDiaria
from app.models.usuario import Usuario
from app.pluggy.client import PluggyError
from app.repositories.transacao import TransacaoRepository
from app.security.current_user import _aware
from app.services import telegram
from app.services.periodo import SP, limites_sp
from app.services.revisao import corte_revisao
from app.services.sync import sincronizar_usuario
from app.telegram_client import TelegramClient, TelegramError

logger = logging.getLogger("app.rotina_diaria")
_em_execucao = threading.Lock()


def recuperar(*, session_factory=SessionLocal, momento: datetime | None = None) -> None:
    """Só no boot, antes de iniciar jobs; não ressuscita relatórios de dias anteriores."""
    hoje = (momento or telegram.agora()).astimezone(SP).date()
    with telegram.lock, session_factory() as db:
        for registro in db.scalars(select(ExecucaoDiaria).where(ExecucaoDiaria.data == hoje)):
            if registro.sync_status == "executando":
                registro.sync_status = "pendente" if registro.tentativas_sync < 3 else "falhou"
            if registro.envio_status == "enviando":
                registro.envio_status, registro.erro = "incerto", "envio_incerto"
                config = db.scalar(
                    select(ConfigTelegram).where(ConfigTelegram.usuario_id == registro.usuario_id)
                )
                if config:
                    config.erro = "envio_incerto"
        db.commit()


def relatorio(db, usuario: Usuario, momento: datetime) -> str | None:
    fim = limites_sp(momento.astimezone(SP).date(), momento.astimezone(SP).date())[1]
    itens, total = TransacaoRepository(db, usuario.id).listar_filtrado(
        fim=fim,
        pendente_revisao=True,
        corte_revisao=corte_revisao(usuario.revisao_desde),
        ocultar_pagamento_fatura=True,
        limit=10,
    )
    if not total:
        return None
    plural = "transação" if total == 1 else "transações"
    linhas = ["Mango · revisão pendente", f"{total} {plural} para revisar", ""]
    for transacao in itens:
        descricao = (
            transacao.descricao_usuario
            or transacao.description
            or transacao.description_raw
            or "Sem descrição"
        )
        descricao = " ".join(descricao.split())[:100]
        valor = transacao.amount_in_account_currency_centavos
        if valor is None:
            valor = transacao.amount_centavos
        sinal = "−" if valor < 0 else "+" if valor > 0 else ""
        reais, centavos = divmod(abs(valor), 100)
        moeda = f"{reais:,}".replace(",", ".") + f",{centavos:02d}"
        data = _aware(transacao.date).astimezone(SP).strftime("%d/%m")
        linhas.append(f"{data} · {descricao} · {sinal}R$ {moeda}")
    linhas.extend(
        [
            "",
            f"Mostrando {len(itens)} de {total}",
            f"Atualizado em {momento.astimezone(SP):%d/%m/%Y %H:%M} (Brasília)",
        ]
    )
    return "\n".join(linhas)


def _enviar(db, usuario_id: int, registro: ExecucaoDiaria, momento: datetime) -> None:
    with telegram.lock:
        db.expire_all()  # preferências podem mudar durante o sync
        geral = telegram.instancia(db)
        usuario = db.get(Usuario, usuario_id)
        config = db.scalar(select(ConfigTelegram).where(ConfigTelegram.usuario_id == usuario_id))
        if (
            registro.envio_status != "pendente"
            or not usuario
            or not usuario.ativo
            or usuario.tipo != "completo"
            or not geral.telegram_ativo
            or not config
            or not config.ativo
            or not config.notif_nao_revisadas
            or not config.chat_id
            or not config.telegram_usuario_id
            or registro.data != momento.astimezone(SP).date()
        ):
            if registro.envio_status == "pendente":
                registro.envio_status = "ignorado"
                db.commit()
            return
        texto = relatorio(db, usuario, momento)
        if texto is None:
            registro.envio_status, registro.proxima_tentativa = "vazio", None
            db.commit()
            return
        # Commit ANTES da chamada: crash depois daqui é incerto, nunca reenvio cego.
        registro.envio_status = "enviando"
        registro.tentativas_envio += 1
        db.commit()
        try:
            with TelegramClient(geral.telegram_token_cifrado) as cliente:
                url = (
                    f"{geral.telegram_url}/transacoes?pendente=true" if geral.telegram_url else None
                )
                cliente.send_message(config.chat_id, texto, url)
        except TelegramError as exc:
            registro.erro = exc.codigo
            registro.proxima_tentativa = None
            if exc.codigo == "envio_incerto":
                registro.envio_status = "incerto"
            elif exc.repetir and registro.tentativas_envio < 3:
                registro.envio_status = "pendente"
                registro.proxima_tentativa = momento + timedelta(seconds=exc.espera)
            else:
                registro.envio_status = "falhou"
            telegram.registrar_erro(db, geral, config, exc)
            logger.warning(
                "rotina usuario=%s data=%s etapa=telegram codigo=%s",
                usuario_id,
                registro.data,
                exc.codigo,
            )
            return
        registro.envio_status, registro.erro, registro.proxima_tentativa = "enviado", None, None
        config.ultimo_envio_em, config.erro = momento, None
        db.commit()


def executar(*, session_factory=SessionLocal, momento: datetime | None = None) -> None:
    if not _em_execucao.acquire(blocking=False):
        return
    try:
        _executar(session_factory, momento)
    finally:
        _em_execucao.release()


def _executar(session_factory, momento: datetime | None) -> None:
    referencia = momento or telegram.agora()
    hoje = referencia.astimezone(SP).date()
    with session_factory() as db:
        geral = telegram.instancia(db)
        if not geral.sync_automatico or referencia.astimezone(SP).time() < geral.sync_horario:
            return
        consulta = select(Usuario.id).where(
            Usuario.ativo.is_(True),
            Usuario.tipo == "completo",
            select(CredencialPluggy.id).where(CredencialPluggy.usuario_id == Usuario.id).exists(),
            select(ItemPluggy.id).where(ItemPluggy.usuario_id == Usuario.id).exists(),
        )
        if settings.app_mode == "local":
            # Mesmo usuário implícito da autenticação; um backup multiusuário não envia por todos.
            local_id = db.scalar(select(Usuario.id).order_by(Usuario.id).limit(1))
            consulta = consulta.where(Usuario.id == local_id)
        usuarios = list(db.scalars(consulta))
    for usuario_id in usuarios:
        agora = momento or telegram.agora()
        if agora.astimezone(SP).date() != hoje:
            break
        try:
            with session_factory() as db:
                if not telegram.instancia(db).sync_automatico:
                    break
                registro = db.scalar(
                    select(ExecucaoDiaria).where(
                        ExecucaoDiaria.usuario_id == usuario_id, ExecucaoDiaria.data == hoje
                    )
                )
                if registro is None:
                    registro = ExecucaoDiaria(usuario_id=usuario_id, data=hoje)
                    db.add(registro)
                    db.commit()
                if registro.proxima_tentativa and _aware(registro.proxima_tentativa) > agora:
                    continue
                if registro.sync_status == "pendente":
                    registro.sync_status = "executando"
                    registro.tentativas_sync += 1
                    registro.proxima_tentativa = None
                    db.commit()
                    try:
                        sincronizar_usuario(db, usuario_id)
                        # Sync-de-todos pode pular itens pelo throttle. Só aceitar os recentes.
                        db.expire_all()
                        itens = db.scalars(
                            select(ItemPluggy).where(ItemPluggy.usuario_id == usuario_id)
                        ).all()
                        limite = agora - timedelta(minutes=settings.sync_min_intervalo_min)
                        if any(
                            it.ultimo_sync_em is None or _aware(it.ultimo_sync_em) < limite
                            for it in itens
                        ):
                            raise ConflictError("sync incompleto")
                    except (PluggyError, ConflictError, RateLimitError):
                        db.rollback()
                        registro.sync_status = (
                            "pendente" if registro.tentativas_sync < 3 else "falhou"
                        )
                        registro.erro = "sync_indisponivel"
                        if registro.tentativas_sync < 3:
                            registro.proxima_tentativa = agora + timedelta(
                                minutes=5 if registro.tentativas_sync == 1 else 15
                            )
                        else:
                            registro.envio_status = "ignorado"
                        db.commit()
                        continue
                    registro.sync_status, registro.erro, registro.proxima_tentativa = (
                        "concluido",
                        None,
                        None,
                    )
                    db.commit()
                if registro.sync_status == "concluido" and registro.envio_status == "pendente":
                    _enviar(db, usuario_id, registro, momento or telegram.agora())
        except Exception:
            # O sync pode ter commits parciais. Marca falha e segue os demais usuários.
            logger.error(
                "rotina usuario=%s data=%s etapa=execucao codigo=erro_interno", usuario_id, hoje
            )
            with session_factory() as db:
                registro = db.scalar(
                    select(ExecucaoDiaria).where(
                        ExecucaoDiaria.usuario_id == usuario_id, ExecucaoDiaria.data == hoje
                    )
                )
                if registro:
                    if registro.envio_status == "enviando":
                        registro.envio_status, registro.erro = "incerto", "envio_incerto"
                    else:
                        registro.sync_status, registro.erro = "falhou", "erro_interno"
                    db.commit()
