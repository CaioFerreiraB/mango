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


def _ativo(db, posicoes) -> Ativo:
    return db.get(Ativo, posicoes[0].ativo_id)


def _objetivos(db, posicoes) -> list[int | None]:
    db.expire_all()
    return [db.get(Investimento, p.id).objetivo_id for p in posicoes]


@pytest.mark.parametrize("enviados", ["todas", "uma"])
def test_vincula_ativo_inteiro_e_lista_uma_linha(
    client_factory, db, usuario_a, posicoes_objetivo, enviados
):
    objetivo, posicoes = posicoes_objetivo
    client = client_factory(usuario_a)
    (grupo,) = client.get("/api/investimentos/resumo").json()["posicoes"]
    assert set(grupo["investimento_ids"]) == {p.id for p in posicoes}
    ids = grupo["investimento_ids"] if enviados == "todas" else [posicoes[0].id]
    corpo = {"objetivo_id": objetivo.id, "investimento_ids": ids}

    # Retry idempotente: os mesmos IDs nunca somam o saldo duas vezes.
    for _ in range(2):
        resposta = client.patch("/api/investimentos/posicao/objetivo", json=corpo)
        assert resposta.status_code == 204, resposta.text
        detalhe = client.get(f"/api/objetivos/{objetivo.id}").json()
        assert detalhe["valor_guardado_centavos"] == 100_000  # conta 40k + 3 compras (60k)
        invs = [v for v in detalhe["vinculos"] if v["tipo"] == "investimento"]
        # Investimento completo: 3 compras do ativo = uma linha (nome do ativo, saldo somado).
        assert [(v["nome"], v["saldo_centavos"]) for v in invs] == [("CDB Reserva", 60_000)]
        assert invs[0]["id"] == posicoes[2].id  # representante = compra de maior saldo
    assert _ativo(db, posicoes).objetivo_id == objetivo.id
    assert _objetivos(db, posicoes) == [objetivo.id] * 3


def test_compra_nova_do_sync_herda_objetivo_do_ativo(db, usuario_a, posicoes_objetivo):
    from app.services.ativo_agrupamento import agrupar_renda_fixa

    objetivo, posicoes = posicoes_objetivo
    investimento_service.definir_objetivo(
        db, usuario_a.id, [posicoes[0].id], objetivo.id, transferir=False
    )
    nova = Investimento(
        usuario_id=usuario_a.id,
        item_id=posicoes[0].item_id,
        pluggy_investment_id="inv-lote-nova",
        nome="Compra 1",  # mesma chave da compra 1 → cai no mesmo ativo
        type="FIXED_INCOME",
        saldo_centavos=5_000,
    )
    db.add(nova)
    db.commit()

    agrupar_renda_fixa(db, usuario_a.id)

    db.refresh(nova)
    assert nova.ativo_id == posicoes[0].ativo_id
    assert nova.objetivo_id == objetivo.id
    assert objetivo_service.obter(db, usuario_a.id, objetivo.id).valor_guardado_centavos == 105_000


def test_mover_compra_segue_o_objetivo_do_ativo_de_destino(
    client_factory, db, usuario_a, posicoes_objetivo
):
    objetivo, posicoes = posicoes_objetivo
    client = client_factory(usuario_a)
    terreno = Ativo(usuario_id=usuario_a.id, nome="Caixinha do terreno")
    db.add(terreno)
    db.commit()
    # Vincula a caixinha (ainda com 1 compra) e depois move outra compra para ela.
    assert client.patch(
        f"/api/investimentos/{posicoes[0].id}", json={"ativo_id": terreno.id}
    ).is_success
    assert client.patch(
        "/api/investimentos/posicao/objetivo",
        json={"objetivo_id": objetivo.id, "investimento_ids": [posicoes[0].id]},
    ).is_success
    assert _objetivos(db, posicoes) == [objetivo.id, None, None]

    resposta = client.patch(f"/api/investimentos/{posicoes[1].id}", json={"ativo_id": terreno.id})
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["objetivo_id"] == objetivo.id
    assert _objetivos(db, posicoes) == [objetivo.id, objetivo.id, None]
    detalhe = client.get(f"/api/objetivos/{objetivo.id}").json()
    assert detalhe["valor_guardado_centavos"] == 70_000  # conta 40k + 10k + 20k
    assert [v["nome"] for v in detalhe["vinculos"] if v["tipo"] == "investimento"] == [
        "Caixinha do terreno"
    ]

    # Sair da caixinha (de volta ao ativo sem vínculo, ou avulsa) deixa de contar.
    client.patch(f"/api/investimentos/{posicoes[1].id}", json={"ativo_id": posicoes[2].ativo_id})
    client.patch(f"/api/investimentos/{posicoes[0].id}", json={"ativo_id": None})
    assert _objetivos(db, posicoes) == [None, None, None]
    assert db.get(Ativo, terreno.id).objetivo_id == objetivo.id  # caixinha segue vinculada


def test_desvincular_uma_compra_desvincula_o_ativo(
    client_factory, db, usuario_a, posicoes_objetivo
):
    objetivo, posicoes = posicoes_objetivo
    outro = ObjetivoRepository(db, usuario_a.id).create(titulo="Outro", valor_alvo_centavos=1)
    client = client_factory(usuario_a)

    # PATCH por id transfere (semântica do MCP) o ativo inteiro.
    client.patch(f"/api/investimentos/{posicoes[1].id}", json={"objetivo_id": outro.id})
    assert _objetivos(db, posicoes) == [outro.id] * 3
    client.patch(f"/api/investimentos/{posicoes[2].id}", json={"objetivo_id": objetivo.id})
    assert _objetivos(db, posicoes) == [objetivo.id] * 3

    resposta = client.patch(f"/api/investimentos/{posicoes[0].id}", json={"objetivo_id": None})
    assert resposta.status_code == 200, resposta.text
    assert _objetivos(db, posicoes) == [None] * 3
    assert _ativo(db, posicoes).objetivo_id is None
    detalhe = client.get(f"/api/objetivos/{objetivo.id}").json()
    assert [v["tipo"] for v in detalhe["vinculos"]] == ["conta"]


@pytest.mark.parametrize("falha", ["conflito", "inexistente", "outro_usuario", "objetivo_alheio"])
def test_vinculo_lote_rejeitado_nao_grava_parte(
    client_factory, db, usuario_a, usuario_b, posicoes_objetivo, falha
):
    objetivo, posicoes = posicoes_objetivo
    dono = usuario_b.id if falha == "objetivo_alheio" else usuario_a.id
    outro = ObjetivoRepository(db, dono).create(titulo="Outro", valor_alvo_centavos=1)
    avulsa = Investimento(
        usuario_id=usuario_a.id,
        item_id=posicoes[0].item_id,
        pluggy_investment_id="inv-avulsa",
        type="MUTUAL_FUND",
        saldo_centavos=1,
    )
    db.add(avulsa)
    db.flush()
    ids = [avulsa.id] + [p.id for p in posicoes]
    if falha == "conflito":
        _ativo(db, posicoes).objetivo_id = outro.id
    elif falha == "inexistente":
        ids.append(999_999)
    elif falha == "outro_usuario":
        posicoes[1].usuario_id = usuario_b.id
    db.commit()
    antes = _objetivos(db, [avulsa, *posicoes]), _ativo(db, posicoes).objetivo_id

    resposta = client_factory(usuario_a).patch(
        "/api/investimentos/posicao/objetivo",
        json={
            "objetivo_id": outro.id if falha == "objetivo_alheio" else objetivo.id,
            "investimento_ids": ids,
        },
    )
    assert resposta.status_code == (409 if falha == "conflito" else 404), resposta.text
    assert (_objetivos(db, [avulsa, *posicoes]), _ativo(db, posicoes).objetivo_id) == antes


def test_vinculo_lote_detecta_mudanca_apos_leitura(
    client_factory, db, usuario_a, posicoes_objetivo, monkeypatch
):
    objetivo, posicoes = posicoes_objetivo
    outro = ObjetivoRepository(db, usuario_a.id).create(titulo="Outro", valor_alvo_centavos=1)
    validar = investimento_service._validar_ids
    ativo_id, outro_id = posicoes[0].ativo_id, outro.id

    def validar_com_mudanca(session, usuario_id, ids):
        resultado = validar(session, usuario_id, ids)
        # Outra sessão vincula o ativo depois da leitura, antes da gravação do lote.
        with Session(db.get_bind()) as concorrente:
            concorrente.execute(
                update(Ativo).where(Ativo.id == ativo_id).values(objetivo_id=outro_id)
            )
            concorrente.commit()
        return resultado

    monkeypatch.setattr(investimento_service, "_validar_ids", validar_com_mudanca)
    resposta = client_factory(usuario_a).patch(
        "/api/investimentos/posicao/objetivo",
        json={"objetivo_id": objetivo.id, "investimento_ids": [p.id for p in posicoes]},
    )
    assert resposta.status_code == 409, resposta.text
    assert _objetivos(db, posicoes) == [None] * 3
    assert _ativo(db, posicoes).objetivo_id == outro_id


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


def test_espelho_e_detalhe_ignoram_ativo_de_outro_usuario(db, usuario_a, usuario_b):
    from app.services.ativo_agrupamento import sincronizar_objetivos_ativos

    objetivo_a = ObjetivoRepository(db, usuario_a.id).create(titulo="A", valor_alvo_centavos=1)
    objetivo_b = ObjetivoRepository(db, usuario_b.id).create(titulo="B", valor_alvo_centavos=1)
    ativo_b = Ativo(usuario_id=usuario_b.id, nome="Ativo de B", objetivo_id=objetivo_b.id)
    db.add(ativo_b)
    conta = criar_conta(db, usuario_a.id, "acc-cruzado")
    # Associação cruzada (não deveria existir): posição de A apontando p/ ativo de B.
    inv = Investimento(
        usuario_id=usuario_a.id,
        item_id=conta.item_id,
        pluggy_investment_id="inv-cruzado",
        nome="Posição de A",
        type="FIXED_INCOME",
        saldo_centavos=1,
        ativo_id=ativo_b.id,
        objetivo_id=objetivo_a.id,
    )
    db.add(inv)
    db.commit()

    (vinculo,) = objetivo_service.obter(db, usuario_a.id, objetivo_a.id).vinculos
    assert vinculo.nome == "Posição de A"  # nunca o nome do ativo de B

    sincronizar_objetivos_ativos(db, usuario_a.id)
    db.commit()
    db.refresh(inv)
    assert inv.objetivo_id == objetivo_a.id  # objetivo de B não vaza para a posição de A


def test_patch_move_e_vincula_atomico(
    client_factory, db, usuario_a, posicoes_objetivo, monkeypatch
):
    from app.exceptions import NotFoundError

    objetivo, posicoes = posicoes_objetivo
    destino = Ativo(usuario_id=usuario_a.id, nome="Destino")
    db.add(destino)
    db.commit()

    def falha(*_):
        raise NotFoundError("objetivo não encontrado")  # p.ex. removido por outra sessão

    monkeypatch.setattr(investimento_service, "_validar_ids", falha)
    resposta = client_factory(usuario_a).patch(
        f"/api/investimentos/{posicoes[0].id}",
        json={"ativo_id": destino.id, "objetivo_id": objetivo.id},
    )
    assert resposta.status_code == 404, resposta.text
    db.expire_all()
    movida = db.get(Investimento, posicoes[0].id)
    assert (movida.ativo_id, movida.objetivo_id) == (posicoes[1].ativo_id, None)
