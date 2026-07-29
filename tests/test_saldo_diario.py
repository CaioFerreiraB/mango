"""Saldo diário: reconstrução via transações, sobreposição por snapshot, exclusão de CREDIT."""

from datetime import time, timedelta

from sqlalchemy.orm import Session

from app.models.cartao_fatura import Cartao
from app.models.saldo_diario import SaldoDiario
from app.models.usuario import Usuario
from app.repositories.conta import ContaRepository
from app.repositories.transacao import TransacaoRepository
from app.services.periodo import SP, hoje_sp
from app.services.saldo_diario import registrar_snapshot, series
from tests.helpers import criar_conta, criar_prereqs_conta


def _em_dia(d):
    """Datetime aware cujo dia civil SP é `d` (meio-dia SP, longe da virada)."""
    from datetime import datetime

    return datetime.combine(d, time(12), tzinfo=SP)


def _tx(repo, conta, pid, amount, quando):
    return repo.create(
        conta_id=conta.id,
        pluggy_transaction_id=pid,
        date=quando,
        amount_centavos=amount,
        currency_code="BRL",
        type="CREDIT" if amount > 0 else "DEBIT",
        status="POSTED",
    )


def test_reconstrucao_backward(db: Session, usuario_a: Usuario) -> None:
    hoje = hoje_sp()
    bank = criar_conta(db, usuario_a.id, "acc-recon", saldo_centavos=100_000)
    repo = TransacaoRepository(db, usuario_a.id)
    _tx(repo, bank, "hoje+5k", 5_000, _em_dia(hoje))
    _tx(repo, bank, "ontem-2k", -2_000, _em_dia(hoje - timedelta(days=1)))

    serie = series(db, usuario_a.id, dias=3)
    assert len(serie) == 1
    pontos = {p.data: p.saldo_centavos for p in serie[0].pontos}
    assert pontos[hoje] == 100_000  # fecho de hoje = saldo atual
    assert pontos[hoje - timedelta(days=1)] == 95_000  # − a entrada de hoje
    assert pontos[hoje - timedelta(days=2)] == 97_000  # − (saída de ontem = −2k)


def test_snapshot_sobrepoe_reconstrucao(db: Session, usuario_a: Usuario) -> None:
    hoje = hoje_sp()
    bank = criar_conta(db, usuario_a.id, "acc-snap", saldo_centavos=100_000)
    repo = TransacaoRepository(db, usuario_a.id)
    _tx(repo, bank, "hoje+5k", 5_000, _em_dia(hoje))
    db.add(
        SaldoDiario(
            usuario_id=usuario_a.id,
            conta_id=bank.id,
            data=hoje - timedelta(days=1),
            saldo_centavos=88_888,
        )
    )
    db.commit()

    pontos = {p.data: p.saldo_centavos for p in series(db, usuario_a.id, dias=3)[0].pontos}
    assert pontos[hoje - timedelta(days=1)] == 88_888  # snapshot vence a reconstrução (95_000)


def test_registrar_snapshot_idempotente(db: Session, usuario_a: Usuario) -> None:
    bank = criar_conta(db, usuario_a.id, "acc-idem", saldo_centavos=10_000)
    registrar_snapshot(db, bank)
    bank.saldo_centavos = 20_000
    registrar_snapshot(db, bank)  # mesmo dia → atualiza, não duplica
    db.commit()
    linhas = db.query(SaldoDiario).filter_by(conta_id=bank.id).all()
    assert len(linhas) == 1 and linhas[0].saldo_centavos == 20_000


def test_series_ignora_cartao(db: Session, usuario_a: Usuario) -> None:
    criar_conta(db, usuario_a.id, "cred-1", type="CREDIT", subtype="CREDIT_CARD")
    assert series(db, usuario_a.id, dias=7) == []  # só contas BANK entram na série


def test_endpoint_lista_traz_brand_level_e_serie(
    client_factory, db: Session, usuario_a: Usuario
) -> None:
    # Uma conta BANK + um cartão do mesmo usuário (credencial/item únicos por usuário → prereqs 1x).
    inst, item = criar_prereqs_conta(db, usuario_a.id)
    repo = ContaRepository(db, usuario_a.id)
    base = {"item_id": item.id, "instituicao_id": inst.id, "currency_code": "BRL"}
    bank = repo.upsert_by_pluggy_id(
        "acc-ep", type="BANK", subtype="CHECKING_ACCOUNT", saldo_centavos=100_000, **base
    )
    credit = repo.upsert_by_pluggy_id(
        "cred-ep", type="CREDIT", subtype="CREDIT_CARD", saldo_centavos=-5_000, **base
    )
    db.add(Cartao(conta_id=credit.id, brand="Mastercard", level="BLACK"))
    db.commit()
    client = client_factory(usuario_a)

    contas = {c["pluggy_account_id"]: c for c in client.get("/api/contas").json()}
    assert contas["cred-ep"]["brand"] == "Mastercard"
    assert contas["cred-ep"]["level"] == "BLACK"
    assert contas["acc-ep"]["brand"] is None  # BANK não tem cartão

    serie = client.get("/api/contas/saldos-diarios?dias=30").json()
    assert len(serie) == 1  # só o BANK
    assert serie[0]["conta_id"] == bank.id
    assert len(serie[0]["pontos"]) == 30
