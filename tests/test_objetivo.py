"""Objetivos (§4.8): CRUD, valor guardado/progresso a partir dos vínculos e isolamento."""

from sqlalchemy.orm import Session

from app.models.investimento import Investimento
from app.models.usuario import Usuario
from app.repositories.objetivo import ObjetivoRepository
from app.services import objetivo as objetivo_service
from tests.helpers import criar_conta


def test_crud_completo(client_factory, usuario_a: Usuario) -> None:
    client = client_factory(usuario_a)

    criado = client.post(
        "/api/objetivos", json={"titulo": "Viagem", "valor_alvo_centavos": 500_000}
    )
    assert criado.status_code == 201, criado.text
    oid = criado.json()["id"]
    assert criado.json()["valor_guardado_centavos"] == 0  # recém-criado, sem vínculo
    assert criado.json()["progresso"] == 0.0

    assert client.get("/api/objetivos").json()[0]["id"] == oid
    assert client.get(f"/api/objetivos/{oid}").json()["vinculos"] == []

    patch = client.patch(f"/api/objetivos/{oid}", json={"valor_alvo_centavos": 600_000})
    assert patch.status_code == 200 and patch.json()["valor_alvo_centavos"] == 600_000

    assert client.delete(f"/api/objetivos/{oid}").status_code == 204
    assert client.get(f"/api/objetivos/{oid}").status_code == 404


def test_valor_guardado_soma_conta_e_investimento(db: Session, usuario_a: Usuario) -> None:
    objetivo = ObjetivoRepository(db, usuario_a.id).create(
        titulo="Reserva", valor_alvo_centavos=100_000
    )
    conta = criar_conta(db, usuario_a.id, "acc-obj", saldo_centavos=40_000)
    conta.objetivo_id = objetivo.id
    db.add(
        Investimento(
            usuario_id=usuario_a.id,
            item_id=conta.item_id,
            pluggy_investment_id="inv-obj",
            type="FIXED_INCOME",
            saldo_centavos=35_000,
            objetivo_id=objetivo.id,
        )
    )
    db.commit()

    detalhe = objetivo_service.obter(db, usuario_a.id, objetivo.id)
    assert detalhe.valor_guardado_centavos == 75_000  # 40k conta + 35k investimento
    assert detalhe.progresso == 0.75
    assert {v.tipo for v in detalhe.vinculos} == {"conta", "investimento"}


def test_progresso_limita_em_um(db: Session, usuario_a: Usuario) -> None:
    objetivo = ObjetivoRepository(db, usuario_a.id).create(
        titulo="Pequeno", valor_alvo_centavos=10_000
    )
    conta = criar_conta(db, usuario_a.id, "acc-cheia", saldo_centavos=50_000)
    conta.objetivo_id = objetivo.id
    db.commit()

    detalhe = objetivo_service.obter(db, usuario_a.id, objetivo.id)
    assert detalhe.valor_guardado_centavos == 50_000
    assert detalhe.progresso == 1.0  # teto, mesmo com guardado > alvo


def test_valor_guardado_isola_usuario(db: Session, usuario_a: Usuario, usuario_b: Usuario) -> None:
    objetivo_a = ObjetivoRepository(db, usuario_a.id).create(
        titulo="A", valor_alvo_centavos=100_000
    )
    # Conta de B com saldo alto, mas apontando para um objetivo de B — nunca deve contar p/ A.
    objetivo_b = ObjetivoRepository(db, usuario_b.id).create(
        titulo="B", valor_alvo_centavos=100_000
    )
    conta_b = criar_conta(db, usuario_b.id, "acc-b", saldo_centavos=999_000)
    conta_b.objetivo_id = objetivo_b.id
    db.commit()

    detalhe = objetivo_service.obter(db, usuario_a.id, objetivo_a.id)
    assert detalhe.valor_guardado_centavos == 0
