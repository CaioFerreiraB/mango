"""Parte Segurança da Fase 1 (S1–S5): IDOR, validação de fronteira, mass-assignment,
não-vazamento de segredo e a guarda de boot. Endpoints via `client_factory` (modo local).
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from app.config import settings
from app.db.bootstrap import _exigir_chaves_de_producao
from app.models.cartao_fatura import Cartao, Fatura
from app.models.pluggy import CredencialPluggy, ItemPluggy
from app.models.usuario import Usuario
from app.repositories.transacao import TransacaoRepository
from tests.helpers import criar_conta

# --- S3: IDOR — recurso de outro usuário some (404, não 403) -------------------------


def test_idor_conta_transacao_fatura_de_outro_usuario(
    db: Session, client_factory, usuario_a: Usuario, usuario_b: Usuario
) -> None:
    conta = criar_conta(db, usuario_a.id, "accA", type="CREDIT", subtype="CREDIT_CARD")
    tx = TransacaoRepository(db, usuario_a.id).create(
        conta_id=conta.id,
        pluggy_transaction_id="tx-a",
        date=datetime.now(UTC),
        amount_centavos=-100,
        currency_code="BRL",
        type="DEBIT",
        status="POSTED",
    )
    db.add(Cartao(conta_id=conta.id, brand="X"))
    db.commit()
    fatura = Fatura(
        usuario_id=usuario_a.id,
        cartao_id=conta.id,
        pluggy_bill_id="bill-a",
        due_date=datetime.now(UTC),
        total_amount_centavos=1000,
    )
    db.add(fatura)
    db.commit()
    db.refresh(fatura)

    b = client_factory(usuario_b)
    assert b.get(f"/api/contas/{conta.id}").status_code == 404
    assert b.get(f"/api/transacoes/{tx.id}").status_code == 404
    assert b.get(f"/api/faturas/{fatura.id}").status_code == 404

    a = client_factory(usuario_a)  # dono continua enxergando
    assert a.get(f"/api/contas/{conta.id}").status_code == 200


def test_sync_de_item_alheio_da_404_sem_rede(
    db: Session, client_factory, usuario_a: Usuario, usuario_b: Usuario
) -> None:
    # A tem uma conexão; B (com credencial própria) tenta sincronizá-la → 404 antes da rede.
    for uid in (usuario_a.id, usuario_b.id):
        db.add(CredencialPluggy(usuario_id=uid, client_id_cifrado="c", client_secret_cifrado="s"))
    db.commit()
    cred_a = db.query(CredencialPluggy).filter_by(usuario_id=usuario_a.id).one()
    item = ItemPluggy(usuario_id=usuario_a.id, credencial_id=cred_a.id, pluggy_item_id="i")
    db.add(item)
    db.commit()
    db.refresh(item)

    b = client_factory(usuario_b)
    assert b.post(f"/api/itens-pluggy/{item.id}/sincronizar").status_code == 404


# --- S4: validação de fronteira ------------------------------------------------------


def test_transacoes_order_limit_offset_validados(client_factory, usuario_a: Usuario) -> None:
    a = client_factory(usuario_a)
    assert a.get("/api/transacoes", params={"order": "senha_hash"}).status_code == 422  # allowlist
    assert a.get("/api/transacoes", params={"limit": 9999}).status_code == 422  # teto 200
    assert a.get("/api/transacoes", params={"offset": -1}).status_code == 422
    ok = a.get("/api/transacoes", params={"order": "amount_centavos", "limit": 10})
    assert ok.status_code == 200
    assert ok.json() == {"items": [], "total": 0}


def test_vincular_transacao_a_assinatura_alheia_barrado(
    db: Session, client_factory, usuario_a: Usuario, usuario_b: Usuario
) -> None:
    """S3/S4: vincular a transação a uma assinatura de OUTRO usuário → 400 (o repo escopado não a
    enxerga). Vincular à própria funciona e aprende o nome da transação como alias (§4.7)."""
    from app.repositories.assinatura import AssinaturaRepository

    conta = criar_conta(db, usuario_a.id, "accA")
    tx = TransacaoRepository(db, usuario_a.id).create(
        conta_id=conta.id,
        pluggy_transaction_id="tx-vinc",
        date=datetime.now(UTC),
        amount_centavos=-2990,
        currency_code="BRL",
        type="DEBIT",
        status="POSTED",
        merchant_nome="NETFLIX*BR",
    )
    ass_b = AssinaturaRepository(db, usuario_b.id).create(
        nome="Netflix", valor_centavos=2990, periodicidade="mensal"
    )
    ass_a = AssinaturaRepository(db, usuario_a.id).create(
        nome="Netflix", valor_centavos=2990, periodicidade="mensal"
    )

    a = client_factory(usuario_a)
    assert a.patch(f"/api/transacoes/{tx.id}", json={"assinatura_id": ass_b.id}).status_code == 400

    ok = a.patch(f"/api/transacoes/{tx.id}", json={"assinatura_id": ass_a.id})
    assert ok.status_code == 200
    assert ok.json()["assinatura_id"] == ass_a.id
    db.expire_all()
    assert db.get(type(ass_a), ass_a.id).nomes_transacao == ["NETFLIX*BR"]  # aprendeu o alias


def test_perfil_ignora_campos_sensiveis(db: Session, client_factory, usuario_a: Usuario) -> None:
    usuario_a.senha_hash = "hash-original"
    db.commit()
    a = client_factory(usuario_a)
    resp = a.patch(
        "/api/perfil",
        json={"nome": "Novo Nome", "senha_hash": "hackeado", "usuario_id": 9999},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["nome"] == "Novo Nome"
    assert "senha_hash" not in body and "totp_secret_cifrado" not in body

    db.expire_all()
    fresh = db.get(Usuario, usuario_a.id)
    assert fresh.senha_hash == "hash-original"  # mass-assignment barrado
    assert fresh.id == usuario_a.id


# --- S1: segredos nunca voltam -------------------------------------------------------


def test_item_read_nao_expoe_itemid(client_factory, usuario_a: Usuario) -> None:
    a = client_factory(usuario_a)
    cred = a.post("/api/credenciais-pluggy", json={"client_id": "c", "client_secret": "s"}).json()
    item = a.post(
        "/api/itens-pluggy",
        json={"credencial_id": cred["id"], "pluggy_item_id": "item-secreto"},
    ).json()
    assert "pluggy_item_id" not in item
    assert "pluggy_item_id" not in a.get(f"/api/itens-pluggy/{item['id']}").json()


# --- S2: guarda de boot (self_hosted não sobe com chave de dev) -----------------------


def test_boot_guard_recusa_chaves_default(monkeypatch) -> None:
    monkeypatch.setattr(settings, "app_mode", "self_hosted")
    with pytest.raises(RuntimeError):
        _exigir_chaves_de_producao()


def test_boot_guard_aceita_chaves_proprias(monkeypatch) -> None:
    monkeypatch.setattr(settings, "app_mode", "self_hosted")
    monkeypatch.setattr(settings, "encryption_key", "chave-propria-de-producao")
    monkeypatch.setattr(settings, "secret_key", "outra-chave-de-producao")
    _exigir_chaves_de_producao()  # não levanta


def test_boot_guard_local_permite_default(monkeypatch) -> None:
    monkeypatch.setattr(settings, "app_mode", "local")
    _exigir_chaves_de_producao()  # local segue com defaults
