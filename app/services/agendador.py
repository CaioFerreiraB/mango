"""Agendador do job mensal de materialização de orçamentos (§4.6, decisão #3).

Só faz sentido no **self-hosted** (container longevo). No desktop o app quase nunca está
aberto no virar do mês; lá a correção vem do backstop (materialização na leitura do consumo
e no fim do sync) — aqui só antecipamos a criação das linhas do mês no dia 1.

O job é idempotente (`materializar_mes` nunca sobrescreve), então mesmo que rode duas vezes
(ex.: dois workers) não duplica nem estraga dados.
"""

from __future__ import annotations

import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.conta import Conta
from app.models.investimento import Investimento
from app.models.usuario import Usuario
from app.services.cvm_fii import atualizar_fundamentos_fii
from app.services.orcamento_mensal import materializar_mes
from app.services.periodo import SP
from app.services.saldo_diario import registrar_snapshot, registrar_snapshot_investimento

logger = logging.getLogger("app.agendador")

_scheduler: BackgroundScheduler | None = None


def materializar_mes_corrente_todos() -> None:
    """Materializa o mês corrente (fuso SP) para todos os usuários. Idempotente."""
    hoje = datetime.now(SP).date()
    db = SessionLocal()
    try:
        for usuario_id in db.scalars(select(Usuario.id)).all():
            materializar_mes(db, usuario_id, hoje.year, hoje.month)
    finally:
        db.close()


def atualizar_fundamentos_fii_todos() -> None:
    """Ingestão mensal dos fundamentos de FII (CVM). Throttled e resiliente (nunca propaga)."""
    db = SessionLocal()
    try:
        atualizar_fundamentos_fii(db)
    finally:
        db.close()


def snapshot_saldos_todos() -> None:
    """Snapshot do saldo atual de cada conta BANK e do valor de cada investimento — garante um
    ponto/dia p/ sparkline e série da carteira mesmo sem sync no dia (carrega o último valor
    conhecido). Idempotente por (conta|investimento, data)."""
    db = SessionLocal()
    try:
        for conta in db.scalars(select(Conta).where(Conta.type == "BANK")).all():
            registrar_snapshot(db, conta)
        for inv in db.scalars(select(Investimento)).all():
            registrar_snapshot_investimento(db, inv)
        db.commit()
    finally:
        db.close()


def iniciar() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler(timezone=SP)
    # Dia 1 de cada mês, 00:05 (SP). `misfire_grace_time` cobre um atraso de boot no virar do mês.
    _scheduler.add_job(
        materializar_mes_corrente_todos,
        trigger="cron",
        day=1,
        hour=0,
        minute=5,
        misfire_grace_time=3600,
        id="materializar_orcamentos",
    )
    # Todo dia 00:10 (SP): ponto diário de saldo por conta para o sparkline dos cards.
    _scheduler.add_job(
        snapshot_saldos_todos,
        trigger="cron",
        hour=0,
        minute=10,
        misfire_grace_time=3600,
        id="snapshot_saldos",
    )
    # Dia 6 de cada mês, 03:00 (SP): fundamentos de FII da CVM (Informe Mensal chega ~15–30d após
    # o mês; o throttle interno evita re-baixar o ZIP sem necessidade). §4.9.
    _scheduler.add_job(
        atualizar_fundamentos_fii_todos,
        trigger="cron",
        day=6,
        hour=3,
        minute=0,
        misfire_grace_time=3600,
        id="fundamentos_fii",
    )
    _scheduler.start()
    logger.info("agendador de orçamentos iniciado")


def parar() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
