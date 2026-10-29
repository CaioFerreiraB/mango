"""Objetivos (§4.8): CRUD, valor guardado/progresso a partir dos vínculos e isolamento."""

import pytest
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.ativo import Ativo
from app.models.investimento import Investimento
from app.models.usuario import Usuario
from app.repositories.objetivo import ObjetivoRepository
from app.services import investimento as investimento_service
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


@pytest.fixture
def posicoes_objetivo(db, usuario_a):
    objetivo = ObjetivoRepository(db, usuario_a.id).create(
        titulo="Reserva", valor_alvo_centavos=100_000
    )
    conta = criar_conta(db, usuario_a.id, "acc-lote", saldo_centavos=40_000)
    conta.objetivo_id = objetivo.id
    ativo = Ativo(usuario_id=usuario_a.id, nome="CDB Reserva")
    db.add(ativo)
    db.flush()
    posicoes = [
        Investimento(
            usuario_id=usuario_a.id,
            item_id=conta.item_id,
            ativo_id=ativo.id,
            pluggy_investment_id=f"inv-lote-{n}",
            nome=f"Compra {n}",
            type="FIXED_INCOME",
            saldo_centavos=n * 10_000,
            amount_centavos=n * 11_000,
        )
        for n in range(1, 4)
    ]
    db.add_all(posicoes)
    db.commit()
    return objetivo, posicoes


def test_vincula_grupo_disponivel_sem_mover_outras_posicoes(
    client_factory, db, usuario_a, posicoes_objetivo
):
    objetivo, posicoes = posicoes_objetivo
    outro = ObjetivoRepository(db, usuario_a.id).create(titulo="Outro", valor_alvo_centavos=1)
    posicoes[2].objetivo_id = outro.id
    db.commit()
    client = client_factory(usuario_a)
    (grupo,) = client.get("/api/investimentos/resumo").json()["posicoes"]
    assert grupo["nome"] == "CDB Reserva"
    assert set(grupo["investimento_ids"]) == {p.id for p in posicoes}
    livres = [p.id for p in posicoes if p.objetivo_id is None]
    corpo = {"objetivo_id": objetivo.id, "investimento_ids": livres}

    # Retry idempotente: os mesmos IDs nunca somam o saldo duas vezes.
    for _ in range(2):
        resposta = client.patch("/api/investimentos/posicao/objetivo", json=corpo)
        assert resposta.status_code == 204, resposta.text
        detalhe = client.get(f"/api/objetivos/{objetivo.id}").json()
        assert detalhe["valor_guardado_centavos"] == 70_000  # conta + saldos, não bruto
        assert detalhe["progresso"] == 0.7
        assert {v["id"] for v in detalhe["vinculos"] if v["tipo"] == "investimento"} == set(livres)
    db.refresh(posicoes[2])
    assert posicoes[2].objetivo_id == outro.id


@pytest.mark.parametrize("falha", ["conflito", "inexistente", "outro_usuario", "objetivo_alheio"])
def test_vinculo_lote_rejeitado_nao_grava_parte(
    client_factory, db, usuario_a, usuario_b, posicoes_objetivo, falha
):
    objetivo, posicoes = posicoes_objetivo
    dono = usuario_b.id if falha == "objetivo_alheio" else usuario_a.id
    outro = ObjetivoRepository(db, dono).create(titulo="Outro", valor_alvo_centavos=1)
    ids = [p.id for p in posicoes]
    if falha == "conflito":
        posicoes[1].objetivo_id = outro.id
    elif falha == "inexistente":
        ids.append(999_999)
    elif falha == "outro_usuario":
        posicoes[1].usuario_id = usuario_b.id
    db.commit()
    antes = {p.id: p.objetivo_id for p in posicoes}

    resposta = client_factory(usuario_a).patch(
        "/api/investimentos/posicao/objetivo",
        json={
            "objetivo_id": outro.id if falha == "objetivo_alheio" else objetivo.id,
            "investimento_ids": ids,
        },
    )
    assert resposta.status_code == (409 if falha == "conflito" else 404), resposta.text
    db.expire_all()
    assert {p.id: p.objetivo_id for p in posicoes} == antes


def test_vinculo_lote_detecta_mudanca_apos_leitura(
    client_factory, db, usuario_a, posicoes_objetivo, monkeypatch
):
    objetivo, posicoes = posicoes_objetivo
    outro = ObjetivoRepository(db, usuario_a.id).create(titulo="Outro", valor_alvo_centavos=1)
    validar = investimento_service._validar_ids
    alterado_id, outro_id = posicoes[1].id, outro.id

    def validar_com_mudanca(session, usuario_id, ids):
        resultado = validar(session, usuario_id, ids)
        # Outra sessão muda o vínculo depois da leitura, antes da gravação do lote.
        with Session(db.get_bind()) as concorrente:
            concorrente.execute(
                update(Investimento)
                .where(Investimento.id == alterado_id)
                .values(objetivo_id=outro_id)
            )
            concorrente.commit()
        return resultado

    monkeypatch.setattr(investimento_service, "_validar_ids", validar_com_mudanca)
    resposta = client_factory(usuario_a).patch(
        "/api/investimentos/posicao/objetivo",
        json={"objetivo_id": objetivo.id, "investimento_ids": [p.id for p in posicoes]},
    )
    assert resposta.status_code == 409, resposta.text
    db.expire_all()
    assert [p.objetivo_id for p in posicoes] == [None, outro_id, None]


@pytest.mark.parametrize(
    "corpo",
    [
        {"objetivo_id": 1, "investimento_ids": []},
        {"objetivo_id": 1, "investimento_ids": [1, 1]},
        {"objetivo_id": 1, "investimento_ids": [0]},
        {"objetivo_id": 1, "investimento_ids": [-1]},
        {"objetivo_id": 1, "investimento_ids": [True]},
        {"objetivo_id": 1, "investimento_ids": ["1"]},
        {"objetivo_id": 1, "investimento_ids": list(range(1, 202))},
        {"objetivo_id": None, "investimento_ids": [1]},
        {"objetivo_id": 0, "investimento_ids": [1]},
    ],
)
def test_vinculo_lote_valida_corpo(client_factory, usuario_a, corpo):
    resposta = client_factory(usuario_a).patch("/api/investimentos/posicao/objetivo", json=corpo)
    assert resposta.status_code == 422, resposta.text
