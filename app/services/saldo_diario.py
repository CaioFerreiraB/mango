"""Saldo diário por conta: snapshot no sync/cron + reconstrução retroativa via transações.

A Pluggy só dá o saldo atual (`conta.saldo_centavos`). A série dos últimos dias é montada assim:
reconstrução `saldo(fecho do dia D) = saldo_atual − Σ(transações com data-SP > D)`, sobreposta pelos
snapshots já gravados (verdade quando presentes). Só contas BANK — ver
`docs/dev/descoberta-saldo-diario-e-imagem-cartao.md`.
"""

from __future__ import annotations

from datetime import UTC, date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.conta import Conta
from app.models.investimento import Investimento
from app.models.investimento_saldo_diario import InvestimentoSaldoDiario
from app.models.saldo_diario import SaldoDiario
from app.models.transacao import Transacao
from app.schemas.conta import ContaSaldoSerie, SaldoDiarioPonto
from app.services.dashboard import _VALOR_EFETIVO
from app.services.periodo import SP, hoje_sp, limites_sp


def registrar_snapshot(db: Session, conta: Conta) -> None:
    """Grava/atualiza o snapshot de hoje (fuso SP) da conta. Idempotente por (conta, data);
    não faz commit — quem chama controla a transação."""
    hoje = hoje_sp()
    existente = db.scalars(
        select(SaldoDiario).where(SaldoDiario.conta_id == conta.id, SaldoDiario.data == hoje)
    ).first()
    if existente is None:
        db.add(
            SaldoDiario(
                usuario_id=conta.usuario_id,
                conta_id=conta.id,
                data=hoje,
                saldo_centavos=conta.saldo_centavos,
            )
        )
        db.flush()  # visível a um SELECT seguinte no mesmo txn (sessão sem autoflush)
    else:
        existente.saldo_centavos = conta.saldo_centavos


def registrar_snapshot_investimento(db: Session, inv: Investimento) -> None:
    """Snapshot de hoje (fuso SP) do investimento — base da série da carteira (§4.9), sem
    reconstrução retroativa (a Pluggy não dá cotação histórica). Idempotente; sem commit."""
    hoje = hoje_sp()
    valor = inv.amount_centavos if inv.amount_centavos is not None else inv.saldo_centavos
    existente = db.scalars(
        select(InvestimentoSaldoDiario).where(
            InvestimentoSaldoDiario.investimento_id == inv.id,
            InvestimentoSaldoDiario.data == hoje,
        )
    ).first()
    if existente is None:
        db.add(
            InvestimentoSaldoDiario(
                usuario_id=inv.usuario_id,
                investimento_id=inv.id,
                data=hoje,
                valor_centavos=valor,
            )
        )
        db.flush()
    else:
        existente.valor_centavos = valor


def series(db: Session, usuario_id: int, dias: int = 30) -> list[ContaSaldoSerie]:
    """Série de `dias` pontos (fecho de cada dia) por conta BANK do usuário."""
    hoje = hoje_sp()
    inicio = hoje - timedelta(days=dias - 1)
    janela = [inicio + timedelta(days=i) for i in range(dias)]

    contas = db.execute(
        select(Conta.id, Conta.saldo_centavos).where(
            Conta.usuario_id == usuario_id, Conta.type == "BANK"
        )
    ).all()
    if not contas:
        return []

    # Δ por conta e dia na janela (amount_centavos já é sinalizado: CREDIT +, DEBIT −).
    ini_utc, fim_utc = limites_sp(inicio, hoje)
    linhas = db.execute(
        select(Transacao.conta_id, Transacao.date, _VALOR_EFETIVO)
        .join(Conta, Conta.id == Transacao.conta_id)
        .where(
            Transacao.usuario_id == usuario_id,
            Conta.type == "BANK",
            Transacao.date >= ini_utc,
            Transacao.date < fim_utc,
        )
    ).all()
    deltas: dict[int, dict[date, int]] = {}
    for conta_id, dt, valor in linhas:
        if dt.tzinfo is None:  # SQLite devolve naive; convenção é UTC
            dt = dt.replace(tzinfo=UTC)
        por_dia = deltas.setdefault(conta_id, {})
        dia = dt.astimezone(SP).date()
        por_dia[dia] = por_dia.get(dia, 0) + valor

    snaps = db.execute(
        select(SaldoDiario.conta_id, SaldoDiario.data, SaldoDiario.saldo_centavos).where(
            SaldoDiario.usuario_id == usuario_id,
            SaldoDiario.data >= inicio,
            SaldoDiario.data <= hoje,
        )
    ).all()
    snap = {(c, d): s for c, d, s in snaps}

    out: list[ContaSaldoSerie] = []
    for conta_id, saldo_atual in contas:
        por_dia = deltas.get(conta_id, {})
        # Reconstrução backward: fecho de hoje = saldo atual; fecho de D−1 = fecho de D − Δ(D).
        fecho: dict[date, int] = {hoje: saldo_atual}
        d = hoje
        while d > inicio:
            fecho[d - timedelta(days=1)] = fecho[d] - por_dia.get(d, 0)
            d -= timedelta(days=1)
        pontos = [
            SaldoDiarioPonto(data=dia, saldo_centavos=snap.get((conta_id, dia), fecho[dia]))
            for dia in janela
        ]
        out.append(ContaSaldoSerie(conta_id=conta_id, pontos=pontos))
    return out
