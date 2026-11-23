"""Divisão ligada a transações + orçamento com investimentos.

Cobre o vínculo (RF01–RF04), a parte do usuário no orçamento/dashboard (RF05–RF07), a lista
mista (RF08–RF10), o relatório do Telegram (RF11) e a aba de investimentos (RF12–RF14).
"""

from datetime import UTC, date, datetime

import pytest
from sqlalchemy.orm import Session

from app.models.categoria import Categoria
from app.models.usuario import Usuario
from app.repositories.transacao import TransacaoRepository
from app.services.dashboard import montar_dashboard
from app.services.orcamento_consumo import consumo_do_mes
from tests.helpers import criar_conta

QUANDO = datetime(2026, 6, 15, 15, tzinfo=UTC)
ALIMENTACAO = "13000000"
INVEST = "03000000"
INVEST_RF = "03020000"
RENDIMENTOS = "03060000"


@pytest.fixture
def cenario(db: Session, usuario_a: Usuario, usuario_b: Usuario):
    db.add_all(
        [
            Categoria(pluggy_id=ALIMENTACAO, description="Alimentação"),
            Categoria(pluggy_id=INVEST, description="Investimentos"),
        ]
    )
    db.flush()
    db.add_all(
        [
            Categoria(pluggy_id=INVEST_RF, description="Renda fixa", parent_id=INVEST),
            Categoria(pluggy_id=RENDIMENTOS, description="Juros", parent_id=INVEST),
        ]
    )
    db.commit()
    conta = criar_conta(db, usuario_a.id, "conta-a")
    return conta


def _tx(db, usuario_id, conta, pid, valor, *, cat=ALIMENTACAO, tipo="DEBIT", quando=QUANDO, **kw):
    return TransacaoRepository(db, usuario_id).create(
        conta_id=conta.id,
        pluggy_transaction_id=pid,
        date=quando,
        amount_centavos=-valor if tipo == "DEBIT" else valor,
        currency_code="BRL",
        type=tipo,
        status="POSTED",
        categoria_pluggy_id=cat,
        **kw,
    )


def _divisao(pago_por: int, participantes: list[int], total: int = 10000, **extra) -> dict:
    return {
        "descricao": "Jantar",
        "categoria_id": ALIMENTACAO,
        "valor_total_centavos": total,
        "pago_por_usuario_id": pago_por,
        "modo_divisao": "igualmente",
        "participantes": participantes,
        "data": QUANDO.isoformat(),
        **extra,
    }


def _orcar(cliente, categoria=ALIMENTACAO, tipo="despesa", limite=100000):
    resp = cliente.post(
        "/api/orcamentos",
        json={"categoria_id": categoria, "tipo": tipo, "limite_padrao_centavos": limite},
    )
    assert resp.status_code == 201, resp.text


def _realizado(db, usuario_id, categoria, tipo="despesa") -> int:
    from app.services.orcamento_mensal import materializar_mes

    materializar_mes(db, usuario_id, 2026, 6)
    consumo = consumo_do_mes(db, usuario_id, 2026, 6)
    return next(
        i.realizado_centavos
        for i in consumo.itens
        if i.categoria_id == categoria and i.tipo == tipo
    )


# --- vínculo (RF01–RF04) --------------------------------------------------------------------


def test_vincular_conta_so_a_minha_parte(client_factory, db, usuario_a, usuario_b, cenario):
    tx = _tx(db, usuario_a.id, cenario, "jantar", 10000)
    a = client_factory(usuario_a)
    _orcar(a)
    assert _realizado(db, usuario_a.id, ALIMENTACAO) == 10000

    resp = a.post(
        "/api/divisoes-despesa",
        json=_divisao(usuario_a.id, [usuario_b.id], transacao_id=tx.id, data=None),
    )
    assert resp.status_code == 201, resp.text
    corpo = resp.json()
    assert corpo["transacao_id"] == tx.id
    assert corpo["data"].startswith("2026-06-15")  # herdou a data da transação
    db.expire_all()
    assert _realizado(db, usuario_a.id, ALIMENTACAO) == 5000
    assert montar_dashboard(
        db, usuario_a.id, date(2026, 6, 1), date(2026, 6, 30)
    ).saidas_centavos == (5000)

    detalhe = a.get(f"/api/transacoes/{tx.id}").json()
    assert detalhe["divisao"] == {
        "id": corpo["id"],
        "valor_total_centavos": 10000,
        "minha_parte_centavos": 5000,
    }

    # Desvincular volta ao valor cheio e a divisão vira pendente.
    resp = a.put(f"/api/divisoes-despesa/{corpo['id']}/vinculo", json={})
    assert resp.status_code == 200, resp.text
    db.expire_all()
    assert _realizado(db, usuario_a.id, ALIMENTACAO) == 10000
    pendentes = a.get("/api/transacoes", params={"pendente_revisao": True}).json()
    assert [i["divisao_id"] for i in pendentes["items"] if i["origem"] == "divisao"] == [
        corpo["id"]
    ]


def test_integral_credor_conta_zero(client_factory, db, usuario_a, usuario_b, cenario):
    tx = _tx(db, usuario_a.id, cenario, "emprestimo", 8000)
    a = client_factory(usuario_a)
    _orcar(a)
    corpo = {
        **_divisao(usuario_a.id, [usuario_b.id], total=8000),
        "modo_divisao": "integral",
        "transacao_id": tx.id,
    }
    assert a.post("/api/divisoes-despesa", json=corpo).status_code == 201
    assert _realizado(db, usuario_a.id, ALIMENTACAO) == 0


def test_vinculo_regras_de_acesso_e_conflito(client_factory, db, usuario_a, usuario_b, cenario):
    tx = _tx(db, usuario_a.id, cenario, "jantar", 10000)
    credito = _tx(db, usuario_a.id, cenario, "pix", 500, tipo="CREDIT")
    conta_b = criar_conta(db, usuario_b.id, "conta-b")
    tx_b = _tx(db, usuario_b.id, conta_b, "jantar-b", 10000)
    a, b = client_factory(usuario_a), client_factory(usuario_b)

    d1 = a.post("/api/divisoes-despesa", json=_divisao(usuario_a.id, [usuario_b.id])).json()
    d2 = a.post("/api/divisoes-despesa", json=_divisao(usuario_a.id, [usuario_b.id])).json()

    # Não-pagador não vincula; transação de outro usuário é invisível (IDOR → 404).
    assert (
        b.put(
            f"/api/divisoes-despesa/{d1['id']}/vinculo", json={"transacao_id": tx_b.id}
        ).status_code
        == 422
    )
    assert (
        a.put(
            f"/api/divisoes-despesa/{d1['id']}/vinculo", json={"transacao_id": tx_b.id}
        ).status_code
        == 404
    )
    # Só saída que não seja transferência.
    assert (
        a.put(
            f"/api/divisoes-despesa/{d1['id']}/vinculo", json={"transacao_id": credito.id}
        ).status_code
        == 422
    )
    # 1 ↔ 1: a mesma transação não serve a duas divisões.
    assert (
        a.put(f"/api/divisoes-despesa/{d1['id']}/vinculo", json={"transacao_id": tx.id}).status_code
        == 200
    )
    assert (
        a.put(f"/api/divisoes-despesa/{d2['id']}/vinculo", json={"transacao_id": tx.id}).status_code
        == 409
    )
    # Transação + "fora do banco" ao mesmo tempo é inválido.
    resp = a.put(
        f"/api/divisoes-despesa/{d2['id']}/vinculo",
        json={"transacao_id": tx.id, "sem_transacao": True},
    )
    assert resp.status_code == 422
    # Só quem paga indica a transação na criação.
    resp = b.post(
        "/api/divisoes-despesa", json=_divisao(usuario_a.id, [usuario_b.id], transacao_id=tx.id)
    )
    assert resp.status_code == 422

    # Escopo "sem_transacao" lista só as minhas sem vínculo.
    ids = [
        d["id"] for d in a.get("/api/divisoes-despesa", params={"escopo": "sem_transacao"}).json()
    ]
    assert ids == [d2["id"]]


def test_vinculo_concorrente_nao_sobrescreve(
    client_factory, session_factory, db, usuario_a, usuario_b, cenario
):
    """Leitura defasada (outra sessão vinculou depois): o compare-and-set recusa com 409 em vez
    de trocar a transação já vinculada — nos dois bancos."""
    from app.exceptions import ConflictError
    from app.models.divisao import DivisaoDespesa
    from app.schemas.divisao import DivisaoVinculo
    from app.services import divisao as divisao_service

    tx1 = _tx(db, usuario_a.id, cenario, "tx1", 10000)
    tx2 = _tx(db, usuario_a.id, cenario, "tx2", 10000)
    a = client_factory(usuario_a)
    d = a.post("/api/divisoes-despesa", json=_divisao(usuario_a.id, [usuario_b.id])).json()

    lenta = session_factory()
    try:
        assert lenta.get(DivisaoDespesa, d["id"]).transacao_id is None  # leu "sem transação"
        assert (
            a.put(
                f"/api/divisoes-despesa/{d['id']}/vinculo", json={"transacao_id": tx1.id}
            ).status_code
            == 200
        )
        with pytest.raises(ConflictError):
            divisao_service.definir_vinculo(
                lenta, usuario_a.id, d["id"], DivisaoVinculo(transacao_id=tx2.id)
            )
    finally:
        lenta.close()
    assert a.get(f"/api/divisoes-despesa/{d['id']}").json()["transacao_id"] == tx1.id


def test_transacao_apagada_devolve_divisao_a_pendencia(
    client_factory, db, usuario_a, usuario_b, cenario
):
    tx = _tx(db, usuario_a.id, cenario, "jantar", 10000)
    a = client_factory(usuario_a)
    d = a.post(
        "/api/divisoes-despesa", json=_divisao(usuario_a.id, [usuario_b.id], transacao_id=tx.id)
    ).json()
    db.delete(tx)
    db.commit()
    assert a.get(f"/api/divisoes-despesa/{d['id']}").json()["transacao_id"] is None


def test_candidatas_mesmo_valor_primeiro_e_sem_vinculadas(
    client_factory, db, usuario_a, usuario_b, cenario
):
    exata = _tx(db, usuario_a.id, cenario, "exata", 10000, quando=datetime(2026, 6, 10, tzinfo=UTC))
    perto = _tx(db, usuario_a.id, cenario, "perto", 9000)
    _tx(db, usuario_a.id, cenario, "longe", 10000, quando=datetime(2026, 5, 1, tzinfo=UTC))
    usada = _tx(db, usuario_a.id, cenario, "usada", 10000)
    a = client_factory(usuario_a)
    a.post(
        "/api/divisoes-despesa", json=_divisao(usuario_a.id, [usuario_b.id], transacao_id=usada.id)
    )

    resp = a.get(
        "/api/divisoes-despesa/transacoes-candidatas",
        params={"valor_centavos": 10000, "data": QUANDO.isoformat()},
    )
    assert resp.status_code == 200, resp.text
    assert [t["id"] for t in resp.json()] == [exata.id, perto.id]


# --- parcelas sem transação no orçamento (RF06) --------------------------------------------


def test_parcela_alheia_e_fora_do_banco_contam(client_factory, db, usuario_a, usuario_b, cenario):
    a, b = client_factory(usuario_a), client_factory(usuario_b)
    _orcar(a)
    # B pagou 10000 dividido com A → 5000 é gasto de A.
    assert (
        b.post("/api/divisoes-despesa", json=_divisao(usuario_b.id, [usuario_a.id])).status_code
        == 201
    )
    assert _realizado(db, usuario_a.id, ALIMENTACAO) == 5000

    # A pagou 3000 "fora do banco" com B → +1500.
    d = a.post(
        "/api/divisoes-despesa", json=_divisao(usuario_a.id, [usuario_b.id], total=3000)
    ).json()
    db.expire_all()
    assert _realizado(db, usuario_a.id, ALIMENTACAO) == 5000  # pendente não soma
    a.put(f"/api/divisoes-despesa/{d['id']}/vinculo", json={"sem_transacao": True})
    db.expire_all()
    assert _realizado(db, usuario_a.id, ALIMENTACAO) == 6500

    # Drill-down soma o realizado.
    drill = a.get(
        "/api/orcamentos/consumo/transacoes",
        params={"ano": 2026, "mes": 6, "tipo": "despesa", "categoria_id": ALIMENTACAO},
    ).json()
    assert sum(i["minha_parte_centavos"] for i in drill["items"]) == 6500


def test_categoria_personalizada_alheia_vira_nao_planejado(
    client_factory, db, usuario_a, usuario_b, cenario
):
    db.add(Categoria(pluggy_id="u_b_1", description="Da B", usuario_id=usuario_b.id))
    db.commit()
    b = client_factory(usuario_b)
    resp = b.post(
        "/api/divisoes-despesa", json=_divisao(usuario_b.id, [usuario_a.id], categoria_id="u_b_1")
    )
    assert resp.status_code == 201, resp.text
    consumo = consumo_do_mes(db, usuario_a.id, 2026, 6)
    assert consumo.nao_planejado_despesa_centavos == 5000
    lista = client_factory(usuario_a).get("/api/transacoes").json()["items"]
    assert lista[0]["categoria_id"] is None


# --- lista mista (RF08–RF10) ---------------------------------------------------------------


def test_lista_mistura_ordena_pagina_e_filtra(client_factory, db, usuario_a, usuario_b, cenario):
    a, b = client_factory(usuario_a), client_factory(usuario_b)
    _tx(db, usuario_a.id, cenario, "antes", 100, quando=datetime(2026, 6, 10, tzinfo=UTC))
    vinculada = _tx(
        db, usuario_a.id, cenario, "depois", 4000, quando=datetime(2026, 6, 20, tzinfo=UTC)
    )
    b.post("/api/divisoes-despesa", json=_divisao(usuario_b.id, [usuario_a.id]))  # 15/06
    a.post(
        "/api/divisoes-despesa",
        json=_divisao(usuario_a.id, [usuario_b.id], total=4000, transacao_id=vinculada.id),
    )

    itens = a.get("/api/transacoes").json()
    assert itens["total"] == 3  # a divisão vinculada aparece como a própria transação
    origens = [(i["origem"], i.get("id") or i["divisao_id"]) for i in itens["items"]]
    assert [o for o, _ in origens] == ["transacao", "divisao", "transacao"]
    assert itens["items"][0]["divisao"]["minha_parte_centavos"] == 2000
    lanc = itens["items"][1]
    assert lanc["pago_por_nome"] == usuario_b.nome
    assert lanc["minha_parte_centavos"] == 5000 and not lanc["pendente"]

    pagina = a.get("/api/transacoes", params={"limit": 1, "offset": 1}).json()
    assert pagina["total"] == 3 and pagina["items"][0]["origem"] == "divisao"

    # Filtro só de transação esconde os lançamentos; "divididas" mostra vinculada + lançamento.
    assert a.get("/api/transacoes", params={"conta_id": cenario.id}).json()["total"] == 2
    divididas = a.get("/api/transacoes", params={"tem_divisao": True}).json()
    assert divididas["total"] == 2
    assert a.get("/api/transacoes", params={"tem_divisao": False}).json()["total"] == 1
    assert a.get("/api/transacoes", params={"busca": "jant"}).json()["total"] == 1

    # Ordem por valor (saída é negativa): o lançamento de 5000 vem antes do de 4000 ascendente.
    por_valor = a.get(
        "/api/transacoes", params={"order": "amount_centavos", "descendente": False}
    ).json()["items"]
    assert por_valor[0]["origem"] == "divisao"


def test_pendente_respeita_corte_de_revisao(client_factory, db, usuario_a, usuario_b, cenario):
    a = client_factory(usuario_a)
    a.post("/api/divisoes-despesa", json=_divisao(usuario_a.id, [usuario_b.id]))
    usuario_a.revisao_desde = date(2026, 7, 1)
    db.commit()
    resp = a.get("/api/transacoes", params={"pendente_revisao": True}).json()
    assert resp["total"] == 0


# --- Telegram (RF11) -----------------------------------------------------------------------


def test_relatorio_inclui_divisoes_e_respeita_toggle(
    db, usuario_a, usuario_b, cenario, client_factory
):
    from app.services.rotina_diaria import relatorio

    a = client_factory(usuario_a)
    a.post("/api/divisoes-despesa", json=_divisao(usuario_a.id, [usuario_b.id], total=12345))
    momento = datetime(2026, 6, 16, 12, tzinfo=UTC)
    texto = relatorio(db, usuario_a, momento)
    assert texto is not None
    assert "Divisões sem transação" in texto and "15/06 · Jantar · R$ 123,45" in texto
    assert relatorio(db, usuario_a, momento, divisoes=False) is None
    # Divisão com data depois do dia do relatório não entra (mesmo corte das transações).
    assert relatorio(db, usuario_a, datetime(2026, 6, 14, 12, tzinfo=UTC)) is None


def test_criar_com_transacao_ja_usada_da_409(client_factory, db, usuario_a, usuario_b, cenario):
    tx = _tx(db, usuario_a.id, cenario, "jantar", 10000)
    a = client_factory(usuario_a)
    corpo = _divisao(usuario_a.id, [usuario_b.id], transacao_id=tx.id)
    assert a.post("/api/divisoes-despesa", json=corpo).status_code == 201
    resp = a.post("/api/divisoes-despesa", json=corpo)
    assert resp.status_code == 409, resp.text
    # Nada da segunda tentativa ficou gravado (divisão + participantes atômicos).
    assert len(a.get("/api/divisoes-despesa").json()) == 1


# --- investimentos (RF12–RF14) -------------------------------------------------------------


def test_investimento_liquido_e_separado_de_despesa(
    client_factory, db, usuario_a, usuario_b, cenario
):
    a = client_factory(usuario_a)
    _tx(db, usuario_a.id, cenario, "aporte", 50000, cat=INVEST_RF)
    _tx(db, usuario_a.id, cenario, "resgate", 20000, cat=INVEST_RF, tipo="CREDIT")
    _tx(db, usuario_a.id, cenario, "juros", 300, cat=RENDIMENTOS, tipo="CREDIT")
    _tx(db, usuario_a.id, cenario, "mercado", 1000)

    # Tipo × categoria.
    resp = a.post(
        "/api/orcamentos",
        json={"categoria_id": INVEST, "tipo": "despesa", "limite_padrao_centavos": 1},
    )
    assert resp.status_code == 422
    resp = a.post(
        "/api/orcamentos",
        json={"categoria_id": ALIMENTACAO, "tipo": "investimento", "limite_padrao_centavos": 1},
    )
    assert resp.status_code == 422
    _orcar(a, INVEST, "investimento", 100000)

    assert _realizado(db, usuario_a.id, INVEST, "investimento") == 30000
    consumo = consumo_do_mes(db, usuario_a.id, 2026, 6)
    assert consumo.nao_planejado_despesa_centavos == 1000  # aporte não é despesa
    assert consumo.nao_planejado_receita_centavos == 300  # só os juros; resgate não é receita
    drill = a.get(
        "/api/orcamentos/consumo/transacoes",
        params={"ano": 2026, "mes": 6, "tipo": "investimento", "categoria_id": INVEST},
    ).json()
    assert {i["pluggy_transaction_id"] for i in drill["items"]} == {"aporte", "resgate"}
