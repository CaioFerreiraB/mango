"""Despesas fixas (docs/dev/despesas-fixas.md): agenda, CRUD, vencimentos, vínculo e resumo."""

from datetime import date, datetime, time

import pytest

from app.models.conta import Conta
from app.models.despesa_fixa import DespesaFixaOcorrencia
from app.models.transacao import Transacao
from app.repositories.transacao import CAMPOS_USUARIO, TransacaoRepository
from app.services.despesa_fixa import vencimentos
from app.services.periodo import SP
from tests.helpers import criar_conta

HOJE = date(2026, 3, 15)


@pytest.fixture
def hoje(monkeypatch):
    """Fixa o "hoje" (fuso SP) das rotas de despesa fixa e do PATCH de transação."""
    for modulo in ("app.routers.despesa_fixa", "app.routers.transacao"):
        monkeypatch.setattr(f"{modulo}.hoje_sp", lambda: HOJE)
    return HOJE


def _datas(freq, dia, inicio, fim=None, n=6):
    gen = vencimentos(freq, dia, inicio, fim)
    return [d for _, d in zip(range(n), gen, strict=False)]


# --- RF03: agenda --------------------------------------------------------------------------------


def test_mensal_dia_31_reajusta_a_cada_mes():
    assert _datas("mensal", 31, date(2027, 1, 1), n=4) == [
        date(2027, 1, 31),
        date(2027, 2, 28),
        date(2027, 3, 31),
        date(2027, 4, 30),
    ]
    assert _datas("mensal", 31, date(2028, 2, 1), n=1) == [date(2028, 2, 29)]  # bissexto


def test_anual_29_de_fevereiro():
    assert _datas("anual", 29, date(2028, 2, 1), n=3) == [
        date(2028, 2, 29),
        date(2029, 2, 28),
        date(2030, 2, 28),
    ]


def test_quinzenal_e_semanal_atravessam_o_mes():
    assert _datas("quinzenal", 25, date(2026, 1, 1), n=3) == [
        date(2026, 1, 25),
        date(2026, 2, 8),
        date(2026, 2, 22),
    ]
    assert _datas("semanal", 30, date(2026, 1, 1), n=2) == [date(2026, 1, 30), date(2026, 2, 6)]


def test_trimestral_semestral_e_fim_da_temporaria():
    assert _datas("trimestral", 10, date(2026, 11, 1), n=3) == [
        date(2026, 11, 10),
        date(2027, 2, 10),
        date(2027, 5, 10),
    ]
    assert _datas("semestral", 5, date(2026, 1, 1), n=2) == [date(2026, 1, 5), date(2026, 7, 5)]
    assert _datas("mensal", 10, date(2026, 1, 1), fim=date(2026, 3, 9), n=10) == [
        date(2026, 1, 10),
        date(2026, 2, 10),
    ]


def test_inicio_depois_do_dia_comeca_no_mes_seguinte():
    assert _datas("mensal", 10, date(2026, 1, 20), n=1) == [date(2026, 2, 10)]


# --- CRUD + validação ----------------------------------------------------------------------------


def _criar(cliente, **campos):
    corpo = {
        "descricao": "Aluguel",
        "valor_centavos": 150_000,
        "frequencia": "mensal",
        "dia_vencimento": 10,
        "inicio": "2026-03-01",
        **campos,
    }
    resp = cliente.post("/api/despesas-fixas", json=corpo)
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.parametrize(
    "campos",
    [
        {"valor_centavos": 0},
        {"dia_vencimento": 0},
        {"dia_vencimento": 32},
        {"frequencia": "diaria"},
        {"fim": "2026-02-01"},
        {"descricao": ""},
    ],
)
def test_criacao_invalida_e_422(client_factory, usuario_a, hoje, campos):
    corpo = {
        "descricao": "Aluguel",
        "valor_centavos": 1,
        "frequencia": "mensal",
        "dia_vencimento": 10,
        "inicio": "2026-03-01",
        **campos,
    }
    assert client_factory(usuario_a).post("/api/despesas-fixas", json=corpo).status_code == 422


def test_criada_no_mes_com_dia_passado_nasce_atrasada(client_factory, usuario_a, hoje):
    cliente = client_factory(usuario_a)
    d = _criar(cliente)  # dia 10, hoje 15/03
    assert d["situacao"] == "atrasada" and d["qtd_atrasos"] == 1
    assert d["proximo_vencimento"] == "2026-04-10"


def test_temporaria_no_passado_so_acompanha_do_mes_atual(client_factory, usuario_a, hoje):
    cliente = client_factory(usuario_a)
    d = _criar(cliente, inicio="2025-06-01", fim="2026-12-31", dia_vencimento=20)
    ocs = cliente.get(f"/api/despesas-fixas/{d['id']}/ocorrencias").json()
    assert [o["vencimento"] for o in ocs] == ["2026-03-20"]
    assert d["qtd_atrasos"] == 0 and d["situacao"] == "em_aberto"


def test_patch_fim_antes_do_inicio_guardado_e_422(client_factory, usuario_a, hoje):
    cliente = client_factory(usuario_a)
    d = _criar(cliente)
    resp = cliente.patch(f"/api/despesas-fixas/{d['id']}", json={"fim": "2026-01-01"})
    assert resp.status_code == 422
    assert (
        cliente.patch(f"/api/despesas-fixas/{d['id']}", json={"valor_centavos": None}).status_code
        == 422
    )


# --- vencimentos ---------------------------------------------------------------------------------


def test_materializacao_idempotente(client_factory, usuario_a, db, hoje):
    cliente = client_factory(usuario_a)
    d = _criar(cliente, frequencia="semanal", dia_vencimento=1)
    for _ in range(3):
        cliente.get("/api/despesas-fixas")
        cliente.get("/api/despesas-fixas/resumo")
    datas = sorted(o.vencimento for o in db.query(DespesaFixaOcorrencia).all())
    # 01, 08, 15 (até hoje) + o próximo futuro 22 — nem um a mais.
    assert datas == [date(2026, 3, d) for d in (1, 8, 15, 22)]
    assert cliente.get(f"/api/despesas-fixas/{d['id']}").json()["qtd_atrasos"] == 2


def test_pagar_pular_reabrir(client_factory, usuario_a, usuario_b, hoje):
    cliente = client_factory(usuario_a)
    d = _criar(cliente)
    (oc,) = [
        o
        for o in cliente.get(f"/api/despesas-fixas/{d['id']}/ocorrencias").json()
        if o["vencimento"] == "2026-03-10"
    ]
    assert oc["situacao"] == "atrasada"
    url = f"/api/despesas-fixas/ocorrencias/{oc['id']}"

    # Outro usuário não alcança o vencimento.
    assert client_factory(usuario_b).patch(url, json={"status": "paga"}).status_code == 404

    pago = cliente.patch(url, json={"status": "paga"}).json()
    assert pago["situacao"] == "paga" and pago["pago_em"] == "2026-03-15"
    assert cliente.get(f"/api/despesas-fixas/{d['id']}").json()["situacao"] == "paga"

    pulado = cliente.patch(url, json={"status": "pulada", "pago_em": "2026-03-01"}).json()
    assert pulado["situacao"] == "pulada" and pulado["pago_em"] is None

    assert cliente.patch(url, json={"status": "aberta"}).json()["situacao"] == "atrasada"
    assert cliente.patch(url, json={"status": "cancelada"}).status_code == 422


def test_editar_valor_refaz_so_futuras_em_aberto(client_factory, usuario_a, hoje):
    cliente = client_factory(usuario_a)
    d = _criar(cliente, valor_centavos=100)
    cliente.patch(f"/api/despesas-fixas/{d['id']}", json={"valor_centavos": 200})
    por_data = {
        o["vencimento"]: o["valor_centavos"]
        for o in cliente.get(f"/api/despesas-fixas/{d['id']}/ocorrencias").json()
    }
    assert por_data == {"2026-03-10": 100, "2026-04-10": 200}  # histórico intacto


def test_desativar_e_reativar_nao_gera_atrasos_do_periodo(client_factory, usuario_a, monkeypatch):
    dia = {"hoje": date(2026, 3, 1)}
    for modulo in ("app.routers.despesa_fixa", "app.routers.transacao"):
        monkeypatch.setattr(f"{modulo}.hoje_sp", lambda: dia["hoje"])
    cliente = client_factory(usuario_a)
    d = _criar(cliente, dia_vencimento=5)
    inativa = cliente.patch(f"/api/despesas-fixas/{d['id']}", json={"ativa": False}).json()
    assert inativa["situacao"] == "inativa" and inativa["proximo_vencimento"] is None

    dia["hoje"] = date(2026, 6, 20)
    assert cliente.get("/api/despesas-fixas/resumo").json()["tem_despesas"] is False
    ativa = cliente.patch(f"/api/despesas-fixas/{d['id']}", json={"ativa": True}).json()
    assert ativa["qtd_atrasos"] == 0 and ativa["proximo_vencimento"] == "2026-07-05"
    datas = [
        o["vencimento"] for o in cliente.get(f"/api/despesas-fixas/{d['id']}/ocorrencias").json()
    ]
    assert datas == ["2026-07-05"]  # 05/03 em diante foi apagada (futura); abr–jun nunca nasceram


# --- vínculo com transação -----------------------------------------------------------------------


def _transacao(db, usuario, pid, dia=date(2026, 3, 12)):
    conta = db.query(Conta).filter_by(usuario_id=usuario.id).first() or criar_conta(
        db, usuario.id, f"acc-df-{usuario.id}"
    )
    return TransacaoRepository(db, usuario.id).create(
        conta_id=conta.id,
        pluggy_transaction_id=f"df-{pid}-{usuario.id}",
        date=datetime.combine(dia, time(12), tzinfo=SP),
        amount_centavos=-150_000,
        currency_code="BRL",
        type="DEBIT",
        status="POSTED",
        eh_transferencia=False,
    )


def test_vinculo_paga_as_mais_antigas_e_desvincular_reabre(client_factory, usuario_a, db, hoje):
    cliente = client_factory(usuario_a)
    d = _criar(cliente, frequencia="semanal", dia_vencimento=1)  # 01, 08 atrasadas; 15 hoje
    t1, t2 = _transacao(db, usuario_a, "a"), _transacao(db, usuario_a, "b")

    r1 = cliente.patch(f"/api/transacoes/{t1.id}", json={"despesa_fixa_id": d["id"]})
    assert r1.status_code == 200, r1.text
    assert r1.json()["despesa_fixa_id"] == d["id"]
    cliente.patch(f"/api/transacoes/{t2.id}", json={"despesa_fixa_id": d["id"]})
    # Repetir o vínculo não paga outro vencimento.
    cliente.patch(f"/api/transacoes/{t2.id}", json={"despesa_fixa_id": d["id"]})

    ocs = {
        o["vencimento"]: o for o in cliente.get(f"/api/despesas-fixas/{d['id']}/ocorrencias").json()
    }
    assert ocs["2026-03-01"]["situacao"] == "paga" and ocs["2026-03-01"]["pago_em"] == "2026-03-12"
    assert ocs["2026-03-08"]["situacao"] == "paga" and ocs["2026-03-08"]["qtd_transacoes"] == 1
    assert ocs["2026-03-15"]["situacao"] == "vence_hoje"

    vinculadas = cliente.get("/api/transacoes", params={"despesa_fixa_id": d["id"]}).json()
    assert {i["id"] for i in vinculadas["items"]} == {t1.id, t2.id}
    assert cliente.get("/api/transacoes", params={"tem_despesa_fixa": False}).json()["total"] == 0

    cliente.patch(f"/api/transacoes/{t1.id}", json={"despesa_fixa_id": None})
    ocs = {
        o["vencimento"]: o for o in cliente.get(f"/api/despesas-fixas/{d['id']}/ocorrencias").json()
    }
    assert ocs["2026-03-01"]["situacao"] == "atrasada" and ocs["2026-03-01"]["pago_em"] is None


def test_vinculo_sem_aberta_paga_o_proximo(client_factory, usuario_a, db, hoje):
    cliente = client_factory(usuario_a)
    d = _criar(cliente, dia_vencimento=20)  # 20/03 em aberto, nenhuma atrasada
    for pid in ("a", "b"):
        t = _transacao(db, usuario_a, pid)
        cliente.patch(f"/api/transacoes/{t.id}", json={"despesa_fixa_id": d["id"]})
    datas = {
        o["vencimento"]: o["situacao"]
        for o in cliente.get(f"/api/despesas-fixas/{d['id']}/ocorrencias").json()
    }
    assert datas == {
        "2026-03-20": "paga",
        "2026-04-20": "paga",  # pagamento antecipado
        "2026-05-20": "aberta",  # o próximo em aberto passa a existir
    }
    assert (
        cliente.get(f"/api/despesas-fixas/{d['id']}").json()["proximo_vencimento"] == "2026-05-20"
    )


def test_vinculo_com_despesa_de_outro_usuario_e_400_sem_gravar(
    client_factory, usuario_a, usuario_b, db, hoje
):
    d_b = _criar(client_factory(usuario_b))
    t = _transacao(db, usuario_a, "x")
    resp = client_factory(usuario_a).patch(
        f"/api/transacoes/{t.id}", json={"despesa_fixa_id": d_b["id"], "revisada": True}
    )
    assert resp.status_code == 400
    db.expire_all()
    salvo = db.get(Transacao, t.id)
    assert salvo.despesa_fixa_id is None and salvo.revisada is False


def test_excluir_despesa_desvincula_transacoes(client_factory, usuario_a, db, hoje):
    cliente = client_factory(usuario_a)
    d = _criar(cliente)
    t = _transacao(db, usuario_a, "z")
    cliente.patch(f"/api/transacoes/{t.id}", json={"despesa_fixa_id": d["id"]})
    assert cliente.delete(f"/api/despesas-fixas/{d['id']}").status_code == 204
    db.expire_all()
    salvo = db.get(Transacao, t.id)
    assert salvo.despesa_fixa_id is None and salvo.despesa_fixa_ocorrencia_id is None
    assert db.query(DespesaFixaOcorrencia).count() == 0


def test_sync_preserva_vinculo():
    assert {"despesa_fixa_id", "despesa_fixa_ocorrencia_id"} <= set(CAMPOS_USUARIO)


# --- RF11/RF19: situação e resumo ----------------------------------------------------------------


def test_resumo_e_situacoes(client_factory, usuario_a, hoje):
    cliente = client_factory(usuario_a)
    semanal = _criar(
        cliente, descricao="Diarista", frequencia="semanal", dia_vencimento=1, valor_centavos=100
    )
    paga = _criar(cliente, descricao="Luz", dia_vencimento=5, valor_centavos=1_000)
    pulada = _criar(cliente, descricao="Clube", dia_vencimento=10, valor_centavos=2_000)
    aberta = _criar(cliente, descricao="Internet", dia_vencimento=20, valor_centavos=3_000)
    _criar(cliente, descricao="IPVA", frequencia="anual", dia_vencimento=1, inicio="2026-05-01")

    def marcar(despesa, status):
        (oc,) = [
            o
            for o in cliente.get(f"/api/despesas-fixas/{despesa['id']}/ocorrencias").json()
            if o["vencimento"].startswith("2026-03")
        ]
        cliente.patch(f"/api/despesas-fixas/ocorrencias/{oc['id']}", json={"status": status})

    marcar(paga, "paga")
    marcar(pulada, "pulada")

    situacao = {
        d["descricao"]: (d["situacao"], d["qtd_atrasos"])
        for d in cliente.get("/api/despesas-fixas").json()
    }
    assert situacao == {
        "Diarista": ("atrasada", 2),
        "Luz": ("paga", 0),
        "Clube": ("pulada", 0),
        "Internet": ("em_aberto", 0),
        "IPVA": ("em_dia", 0),
    }

    r = cliente.get("/api/despesas-fixas/resumo").json()
    assert r["mes"] == "2026-03" and r["tem_despesas"] is True
    assert r["pagas"] == {"qtd": 1, "centavos": 1_000}
    assert r["atrasadas"] == {"qtd": 2, "centavos": 200}
    assert r["abertas"] == {"qtd": 3, "centavos": 100 + 100 + 3_000}  # 15 (hoje), 22 e 20/03
    assert r["puladas"] == 1
    assert [(p["descricao"], p["vencimento"], p["situacao"]) for p in r["proximos"]] == [
        ("Diarista", "2026-03-01", "atrasada"),
        ("Diarista", "2026-03-08", "atrasada"),
        ("Diarista", "2026-03-15", "vence_hoje"),
        ("Internet", "2026-03-20", "aberta"),
        ("Luz", "2026-04-05", "aberta"),
    ]
    assert semanal and aberta


def test_nao_reabre_nem_pula_vencimento_pago_por_transacao(client_factory, usuario_a, db, hoje):
    cliente = client_factory(usuario_a)
    d = _criar(cliente)
    t = _transacao(db, usuario_a, "r")
    cliente.patch(f"/api/transacoes/{t.id}", json={"despesa_fixa_id": d["id"]})
    (oc,) = [
        o
        for o in cliente.get(f"/api/despesas-fixas/{d['id']}/ocorrencias").json()
        if o["vencimento"] == "2026-03-10"
    ]
    url = f"/api/despesas-fixas/ocorrencias/{oc['id']}"
    for status in ("aberta", "pulada"):
        assert cliente.patch(url, json={"status": status}).status_code == 409
    # Desvinculando, volta a poder.
    cliente.patch(f"/api/transacoes/{t.id}", json={"despesa_fixa_id": None})
    assert cliente.patch(url, json={"status": "pulada"}).status_code == 200


def test_mudar_agenda_nao_cria_vencimentos_passados(client_factory, usuario_a, hoje):
    cliente = client_factory(usuario_a)
    d = _criar(cliente, frequencia="semanal", dia_vencimento=1)  # 01, 08, 15, 22
    cliente.patch(f"/api/despesas-fixas/{d['id']}", json={"dia_vencimento": 3})
    datas = sorted(
        o["vencimento"] for o in cliente.get(f"/api/despesas-fixas/{d['id']}/ocorrencias").json()
    )
    # Histórico (01, 08) intacto; 15 (hoje, aberta) refeito; nada de 03/03 ou 10/03 retroativos.
    assert datas == ["2026-03-01", "2026-03-08", "2026-03-17"]
