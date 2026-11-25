"""Aviso de despesa fixa no Telegram (docs/dev/despesas-fixas.md, RF16–RF18).

Uma mensagem por usuário com "Vence hoje" e "Atrasadas". "Vence hoje" sai uma vez por vencimento
(`aviso_hoje_em`); atraso, uma vez por dia até pagar/pular (`aviso_atraso_em`). Só a partir do
horário da rotina diária (`sync_horario`), independente do sync automático estar ligado. Mesmo
protocolo de `orcamento_alerta`: marca e comita ANTES do envio; falha certa desfaz a marca.
"""

from __future__ import annotations

import logging
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.despesa_fixa import DespesaFixa, DespesaFixaOcorrencia
from app.models.telegram import ConfigTelegram
from app.models.usuario import Usuario
from app.services import telegram
from app.services.despesa_fixa import materializar
from app.services.orcamento_alerta import _brl
from app.services.periodo import SP
from app.services.rotina_diaria import _url_do_botao
from app.telegram_client import TelegramClient, TelegramError

logger = logging.getLogger("app.despesa_fixa_alerta")


def verificar_e_avisar(db: Session, usuario_id: int, momento: datetime | None = None) -> int:
    """Envia o aviso do dia, se houver o que avisar. Devolve quantos vencimentos entraram na
    mensagem. Nunca propaga erro do Telegram."""
    momento = momento or telegram.agora()
    local = momento.astimezone(SP)
    hoje = local.date()
    with telegram.lock:
        geral = telegram.instancia(db)
        usuario = db.get(Usuario, usuario_id)
        config = db.scalar(select(ConfigTelegram).where(ConfigTelegram.usuario_id == usuario_id))
        if (
            not telegram.pronto(geral, config, usuario)
            or not config.notif_despesas_fixas
            or local.time() < geral.sync_horario
        ):
            return 0

        vence_hoje, atrasadas = _a_avisar(db, usuario_id, hoje)
        if not vence_hoje and not atrasadas:
            return 0

        # Marca ANTES do envio: crash depois daqui vira "não avisado", nunca reenvio em loop.
        antes = {oc.id: (oc.aviso_hoje_em, oc.aviso_atraso_em) for oc, _ in vence_hoje + atrasadas}
        for oc, _ in vence_hoje:
            oc.aviso_hoje_em = momento
        for oc, _ in atrasadas:
            oc.aviso_atraso_em = hoje
        db.commit()

        texto = _mensagem(vence_hoje, atrasadas, hoje)
        try:
            with TelegramClient(geral.telegram_token_cifrado) as cliente:
                cliente.send_message(
                    config.chat_id, texto, _url_do_botao(geral.telegram_url, "/despesas-fixas")
                )
        except TelegramError as exc:
            if exc.codigo != "envio_incerto":
                for oc, _ in vence_hoje + atrasadas:
                    oc.aviso_hoje_em, oc.aviso_atraso_em = antes[oc.id]
                db.commit()
            telegram.registrar_erro(db, geral, config, exc)
            logger.warning("aviso de despesa fixa usuario=%s codigo=%s", usuario_id, exc.codigo)
            return 0
        return len(vence_hoje) + len(atrasadas)


def _a_avisar(db: Session, usuario_id: int, hoje: date) -> tuple[list, list]:
    """(vence hoje ainda não avisadas, atrasadas não avisadas hoje) das despesas ativas."""
    materializar(db, usuario_id, hoje)
    linhas = db.execute(
        select(DespesaFixaOcorrencia, DespesaFixa.descricao)
        .join(DespesaFixa, DespesaFixa.id == DespesaFixaOcorrencia.despesa_fixa_id)
        .where(
            DespesaFixaOcorrencia.usuario_id == usuario_id,
            DespesaFixa.ativa,
            DespesaFixaOcorrencia.status == "aberta",
            DespesaFixaOcorrencia.vencimento <= hoje,
        )
        .order_by(DespesaFixaOcorrencia.vencimento, DespesaFixaOcorrencia.id)
    ).all()
    vence_hoje = [(oc, d) for oc, d in linhas if oc.vencimento == hoje and oc.aviso_hoje_em is None]
    atrasadas = [
        (oc, d)
        for oc, d in linhas
        if oc.vencimento < hoje and (oc.aviso_atraso_em is None or oc.aviso_atraso_em < hoje)
    ]
    return vence_hoje, atrasadas


# Teto do Telegram é 4096 caracteres: lista no máximo isto (as marcas valem para todas) e corta a
# descrição. 15 linhas × ~110 caracteres cabe com folga.
_MAX_ITENS = 15
_MAX_DESCRICAO = 60


def _curta(texto: str) -> str:
    return texto if len(texto) <= _MAX_DESCRICAO else texto[: _MAX_DESCRICAO - 1] + "…"


def _mensagem(
    vence_hoje: list[tuple[DespesaFixaOcorrencia, str]],
    atrasadas: list[tuple[DespesaFixaOcorrencia, str]],
    hoje: date,
) -> str:
    partes = ["**Mango · despesas fixas**"]
    vagas = _MAX_ITENS
    if vence_hoje:
        partes += ["", "**Vence hoje**"]
        partes += [f"• {_curta(d)} · {_brl(oc.valor_centavos)}" for oc, d in vence_hoje[:vagas]]
        vagas = max(0, vagas - len(vence_hoje))
    if atrasadas:
        partes += ["", f"**Atrasadas ({len(atrasadas)})**"]
        for oc, d in atrasadas[:vagas]:
            dias = (hoje - oc.vencimento).days
            atraso = "1 dia" if dias == 1 else f"{dias} dias"
            venceu = f"venceu {oc.vencimento:%d/%m} ({atraso})"
            partes.append(f"• {_curta(d)} · {_brl(oc.valor_centavos)} · {venceu}")
    fora = len(vence_hoje) + len(atrasadas) - _MAX_ITENS
    if fora > 0:
        partes += ["", f"… e mais {fora}. Veja todas na página Despesas fixas."]
    return "\n".join(partes)


def verificar_todos(*, session_factory=SessionLocal, momento: datetime | None = None) -> None:
    """Job do agendador: avisa cada usuário com Telegram ativo. Falha de um não para os demais."""
    with session_factory() as db:
        usuarios = db.scalars(
            select(ConfigTelegram.usuario_id).where(
                ConfigTelegram.ativo, ConfigTelegram.notif_despesas_fixas
            )
        ).all()
    for usuario_id in usuarios:
        try:
            with session_factory() as db:
                verificar_e_avisar(db, usuario_id, momento)
        except Exception:
            logger.exception("aviso de despesa fixa falhou usuario=%s", usuario_id)
