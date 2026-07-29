"""Pareamento de transferências e detecção de pagamento de fatura (§4.2/§4.4).

Roda em SQLite e Postgres (fixture `db`).
"""

from datetime import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session

from app.models.categoria import Categoria
from app.models.pluggy import CredencialPluggy, Instituicao, ItemPluggy
from app.models.transacao import TransacaoPagamento
from app.models.usuario import Usuario
from app.repositories.conta import ContaRepository
from app.repositories.transacao import TransacaoRepository
from app.services.transferencia import aplicar_regras_transferencia


@pytest.fixture
def usuario(db: Session) -> Usuario:
    u = Usuario(nome="T", email="t@mango.test")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture
def cenario(db: Session, usuario: Usuario) -> SimpleNamespace:
    """Usuário com duas contas conectadas + categorias-chave semeadas."""
    for cid in ["04020000", "05100000", "07010000"]:
        db.add(Categoria(pluggy_id=cid, description=cid))
    inst = Instituicao(usuario_id=usuario.id, nome="Banco", pluggy_connector_id=1)
    cred = CredencialPluggy(usuario_id=usuario.id, client_id_cifrado="c", client_secret_cifrado="s")
    db.add_all([inst, cred])
    db.commit()
    db.refresh(inst)
    db.refresh(cred)
    item = ItemPluggy(usuario_id=usuario.id, credencial_id=cred.id, pluggy_item_id="i")
    db.add(item)
    db.commit()
    db.refresh(item)

    conta_repo = ContaRepository(db, usuario.id)
    base = {
        "item_id": item.id,
        "instituicao_id": inst.id,
        "type": "BANK",
        "subtype": "CHECKING_ACCOUNT",
        "saldo_centavos": 0,
        "currency_code": "BRL",
    }
    a = conta_repo.upsert_by_pluggy_id("accA", **base)
    b = conta_repo.upsert_by_pluggy_id("accB", **base)
    return SimpleNamespace(
        usuario=usuario, a=a, b=b, repo=TransacaoRepository(db, usuario.id)
    )


def _tx(repo, conta, pid, amount, *, cat=None, dia=15, **extra):
    return repo.create(
        conta_id=conta.id,
        pluggy_transaction_id=pid,
        date=datetime(2026, 6, dia),
        amount_centavos=amount,
        currency_code="BRL",
        type="CREDIT" if amount > 0 else "DEBIT",
        status="POSTED",
        categoria_pluggy_id=cat,
        **extra,
    )


def test_pareia_duas_pernas_mesma_titularidade(db, cenario):
    saida = _tx(cenario.repo, cenario.a, "out", -50_000, cat="04020000", dia=15)
    entrada = _tx(cenario.repo, cenario.b, "in", 50_000, cat="04020000", dia=16)

    aplicar_regras_transferencia(db, cenario.usuario.id)
    db.refresh(saida)
    db.refresh(entrada)

    assert saida.eh_transferencia and entrada.eh_transferencia
    assert saida.contraparte_id == entrada.id
    assert entrada.contraparte_id == saida.id
    assert saida.transferencia_origem == "auto"


def test_pagamento_de_fatura_marca_transferencia(db, cenario):
    pag = _tx(cenario.repo, cenario.a, "pgto", -30_000, cat="05100000")

    aplicar_regras_transferencia(db, cenario.usuario.id)
    db.refresh(pag)

    assert pag.eh_transferencia is True  # caixa: não recontabiliza (§4.2)
    assert pag.transferencia_origem == "auto"
    assert pag.contraparte_id is None  # perna única


def test_perna_unica_nao_pareia(db, cenario):
    solo = _tx(cenario.repo, cenario.a, "solo", -20_000, cat="04020000")

    aplicar_regras_transferencia(db, cenario.usuario.id)
    db.refresh(solo)

    assert solo.eh_transferencia is False  # sem contraparte → transação comum
    assert solo.contraparte_id is None


def test_flag_manual_nao_e_sobrescrito(db, cenario):
    # Usuário disse explicitamente que NÃO é transferência (manual).
    manual = _tx(
        cenario.repo, cenario.a, "man", -50_000, cat="04020000",
        transferencia_origem="manual", eh_transferencia=False,
    )
    _tx(cenario.repo, cenario.b, "in", 50_000, cat="04020000")

    aplicar_regras_transferencia(db, cenario.usuario.id)
    db.refresh(manual)

    assert manual.eh_transferencia is False
    assert manual.contraparte_id is None


def test_pareia_por_documento_quando_nao_ha_categoria(db, cenario):
    # Sem 04x, mas o mesmo CPF aparece nas duas pernas (paymentData) → pareia.
    saida = _tx(cenario.repo, cenario.a, "out", -70_000, cat="07010000", dia=10)
    entrada = _tx(cenario.repo, cenario.b, "in", 70_000, cat="07010000", dia=10)
    db.add(TransacaoPagamento(transacao_id=saida.id, payer_doc_valor="111.111.111-11"))
    db.add(TransacaoPagamento(transacao_id=entrada.id, receiver_doc_valor="111.111.111-11"))
    db.commit()

    aplicar_regras_transferencia(db, cenario.usuario.id)
    db.refresh(saida)
    db.refresh(entrada)

    assert saida.contraparte_id == entrada.id
    assert saida.eh_transferencia and entrada.eh_transferencia


def test_valor_diferente_nao_pareia(db, cenario):
    saida = _tx(cenario.repo, cenario.a, "out", -50_000, cat="04020000")
    entrada = _tx(cenario.repo, cenario.b, "in", 40_000, cat="04020000")

    aplicar_regras_transferencia(db, cenario.usuario.id)
    db.refresh(saida)
    db.refresh(entrada)

    assert saida.contraparte_id is None
    assert entrada.contraparte_id is None
