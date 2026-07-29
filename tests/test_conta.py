"""Conta (Pluggy-owned): upsert idempotente, re-sync, update estreito e isolamento."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.cartao_fatura import Cartao, Fatura
from app.models.usuario import Usuario
from app.repositories.conta import ContaRepository
from app.repositories.objetivo import ObjetivoRepository
from tests.helpers import criar_conta


def test_upsert_idempotente_e_resync_preserva_objetivo(db: Session, usuario_a: Usuario) -> None:
    conta = criar_conta(db, usuario_a.id, "acc-1", saldo_centavos=10000)
    assert conta.saldo_centavos == 10000

    # Usuário vincula um objetivo (campo do usuário).
    objetivo = ObjetivoRepository(db, usuario_a.id).create(
        titulo="Reserva", descricao=None, justificativa=None, valor_alvo_centavos=500000
    )
    repo = ContaRepository(db, usuario_a.id)
    repo.update(conta, objetivo_id=objetivo.id)

    # Re-sync (novo saldo, mesma pluggy_account_id) NÃO sobrescreve o objetivo do usuário.
    conta2 = repo.upsert_by_pluggy_id(
        "acc-1",
        item_id=conta.item_id,
        instituicao_id=conta.instituicao_id,
        type="BANK",
        subtype="CHECKING_ACCOUNT",
        saldo_centavos=20000,
        currency_code="BRL",
        objetivo_id=None,
    )
    assert conta2.id == conta.id
    assert conta2.saldo_centavos == 20000
    assert conta2.objetivo_id == objetivo.id


def test_vinculo_objetivo_via_api(client_factory, db: Session, usuario_a: Usuario) -> None:
    conta = criar_conta(db, usuario_a.id, "acc-api")
    objetivo = ObjetivoRepository(db, usuario_a.id).create(
        titulo="Meta", descricao=None, justificativa=None, valor_alvo_centavos=1000
    )
    client = client_factory(usuario_a)

    assert client.get("/api/contas").status_code == 200
    resp = client.patch(f"/api/contas/{conta.id}", json={"objetivo_id": objetivo.id})
    assert resp.status_code == 200, resp.text
    assert resp.json()["objetivo_id"] == objetivo.id

    # desvincular
    resp = client.patch(f"/api/contas/{conta.id}", json={"objetivo_id": None})
    assert resp.json()["objetivo_id"] is None


def test_nao_vincula_objetivo_de_outro_usuario(
    client_factory, db: Session, usuario_a: Usuario, usuario_b: Usuario
) -> None:
    conta = criar_conta(db, usuario_a.id, "acc-cross")
    objetivo_b = ObjetivoRepository(db, usuario_b.id).create(
        titulo="de B", descricao=None, justificativa=None, valor_alvo_centavos=1
    )
    client_a = client_factory(usuario_a)
    # Objetivo de B não existe para A → 404 (não vaza entre usuários).
    resp = client_a.patch(f"/api/contas/{conta.id}", json={"objetivo_id": objetivo_b.id})
    assert resp.status_code == 404


def test_faturas_resumo_via_api(client_factory, db: Session, usuario_a: Usuario) -> None:
    conta = criar_conta(db, usuario_a.id, "acc-fat", type="CREDIT", subtype="CREDIT_CARD")
    db.add(Cartao(conta_id=conta.id))
    db.add(
        Fatura(
            usuario_id=usuario_a.id,
            cartao_id=conta.id,
            pluggy_bill_id="bill-1",
            due_date=datetime(2026, 7, 15, tzinfo=UTC),
            total_amount_centavos=42_000,
        )
    )
    db.commit()

    resp = client_factory(usuario_a).get(f"/api/contas/{conta.id}/faturas-resumo")
    assert resp.status_code == 200, resp.text
    buckets = resp.json()["buckets"]
    assert [b["total_centavos"] for b in buckets] == [42_000]
    assert buckets[0]["due_date"] == "2026-07-15"
    # Sem compras sincronizadas: o ajuste sozinho fecha a quebra no total.
    assert sum(g["total_centavos"] for g in buckets[0]["por_categoria"]) == 42_000


def test_faturas_resumo_isolado(
    client_factory, db: Session, usuario_a: Usuario, usuario_b: Usuario
) -> None:
    conta = criar_conta(db, usuario_a.id, "acc-fat-iso", type="CREDIT", subtype="CREDIT_CARD")
    assert (
        client_factory(usuario_b).get(f"/api/contas/{conta.id}/faturas-resumo").status_code == 404
    )


def test_isolamento_conta_via_api(
    client_factory, db: Session, usuario_a: Usuario, usuario_b: Usuario
) -> None:
    conta = criar_conta(db, usuario_a.id, "acc-iso", type="CREDIT", subtype="CREDIT_CARD")
    client_b = client_factory(usuario_b)

    assert client_b.get("/api/contas").json() == []
    assert client_b.get(f"/api/contas/{conta.id}").status_code == 404
    assert client_b.patch(f"/api/contas/{conta.id}", json={"objetivo_id": None}).status_code == 404
