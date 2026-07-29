"""Investimentos (Fase 3, §4.9): sync + snapshot, resumo/proventos/série server-side e
isolamento das rotas novas. Cliente Pluggy mockado (FakePluggy de `test_sync`); roda em
SQLite e Postgres (fixture `db`)."""

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.ativo import Ativo
from app.models.investimento import Investimento, InvestimentoTransacao
from app.models.investimento_saldo_diario import InvestimentoSaldoDiario
from app.models.objetivo import Objetivo
from app.models.pluggy import CredencialPluggy, ItemPluggy
from app.models.usuario import Usuario
from app.repositories.investimento import InvestimentoRepository
from app.services import investimento as carteira
from app.services import sync as sync_mod
from app.services.ativo_agrupamento import agrupar_renda_fixa
from app.services.sync import sincronizar_usuario
from tests.test_sync import CDB_ID, FII_ID, FakePluggy


@pytest.fixture
def usuario(db: Session) -> Usuario:
    u = Usuario(nome="Investidor", email="inv@mango.test")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture
def conexao(db: Session, usuario: Usuario) -> ItemPluggy:
    cred = CredencialPluggy(
        usuario_id=usuario.id, client_id_cifrado="cid", client_secret_cifrado="secret"
    )
    db.add(cred)
    db.commit()
    db.refresh(cred)
    item = ItemPluggy(usuario_id=usuario.id, credencial_id=cred.id, pluggy_item_id="item-x")
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@pytest.fixture(autouse=True)
def _mock_pluggy(monkeypatch):
    monkeypatch.setattr(sync_mod, "PluggyClient", lambda *a, **k: FakePluggy())
    sync_mod._em_andamento.clear()


# --- sync -----------------------------------------------------------------------------


def test_sync_importa_investimentos_e_movimentos(db, usuario, conexao):
    sincronizar_usuario(db, usuario.id)

    invs = {i.pluggy_investment_id: i for i in db.scalars(select(Investimento)).all()}
    assert set(invs) == {FII_ID, CDB_ID}

    fii = invs[FII_ID]
    assert fii.type == "EQUITY" and fii.subtype == "REAL_ESTATE_FUND"
    assert fii.amount_centavos == 11_840  # 118.40 → centavos
    assert fii.amount_original_centavos == 11_900
    assert fii.quantity == Decimal(1)
    assert fii.instituicao_emissora_nome == "Corretora X"

    cdb = invs[CDB_ID]
    assert cdb.amount_centavos == 105_025
    assert cdb.taxes_centavos == 1_050  # IR consumido do Pluggy (#5)
    assert cdb.taxes2_centavos == 55
    assert cdb.rate == Decimal(110)

    movs = db.scalars(
        select(InvestimentoTransacao).where(InvestimentoTransacao.investimento_id == fii.id)
    ).all()
    assert {m.pluggy_id for m in movs} == {"itx-compra", "itx-dividendo"}
    dividendo = next(m for m in movs if m.pluggy_id == "itx-dividendo")
    # type fora de BUY/SELL persiste (CHECK relaxado na Fase 3 p/ proventos reais)
    assert dividendo.type == "DIVIDEND" and dividendo.movement_type == "CREDIT"
    assert dividendo.amount_centavos == 1_234


def test_resync_preserva_objetivo_e_snapshot_idempotente(db, usuario, conexao):
    sincronizar_usuario(db, usuario.id)
    repo = InvestimentoRepository(db, usuario.id)
    fii = repo.get_by_pluggy_id(FII_ID)

    objetivo = Objetivo(usuario_id=usuario.id, titulo="Aposentadoria", valor_alvo_centavos=10)
    db.add(objetivo)
    db.commit()
    repo.update(fii, objetivo_id=objetivo.id)

    sincronizar_usuario(db, usuario.id, forcar=True)
    db.refresh(fii)
    assert fii.objetivo_id == objetivo.id  # re-sync não sobrescreve vínculo do usuário (#4)

    # dois syncs no mesmo dia → um snapshot por investimento (upsert por (inv, data))
    snaps = db.scalars(select(InvestimentoSaldoDiario)).all()
    assert len(snaps) == 2
    assert {s.valor_centavos for s in snaps} == {11_840, 105_025}
    # movimentos também não duplicam
    assert len(db.scalars(select(InvestimentoTransacao)).all()) == 2


# --- resumo / proventos / transações (rotas) ------------------------------------------


def test_resumo_carteira(db, usuario, conexao, usuario_b, client_factory):
    sincronizar_usuario(db, usuario.id)
    resumo = client_factory(usuario).get("/api/investimentos/resumo").json()

    assert resumo["totais"]["valor_centavos"] == 116_865
    assert resumo["totais"]["investido_centavos"] == 111_900
    # FII sem amountProfit → fallback amount−investido (−60); CDB traz 5025 → 4965
    assert resumo["totais"]["resultado_centavos"] == 4_965
    assert resumo["totais"]["quantidade_ativos"] == 2

    assert [a["tipo"] for a in resumo["alocacao"]] == ["CDB", "REAL_ESTATE_FUND"]
    assert resumo["alocacao"][0]["pct"] == pytest.approx(89.87, abs=0.01)

    (ativo,) = resumo["renda_variavel"]
    assert ativo["code"] == "GGRC11"
    assert ativo["quantidade"] == 1
    assert ativo["preco_medio_centavos"] == 11_900
    assert ativo["valorizacao_centavos"] == -60
    assert ativo["valorizacao_pct"] == pytest.approx(-0.5, abs=0.01)

    assert [g["type"] for g in resumo["grupos"]] == ["FIXED_INCOME", "EQUITY"]

    # isolamento: B tem carteira vazia
    resumo_b = client_factory(usuario_b).get("/api/investimentos/resumo").json()
    assert resumo_b["totais"]["quantidade_ativos"] == 0
    assert resumo_b["totais"]["valor_centavos"] == 0


def test_proventos_fii_e_dy(db, usuario, conexao, usuario_b, client_factory):
    sincronizar_usuario(db, usuario.id)
    fii = InvestimentoRepository(db, usuario.id).get_by_pluggy_id(FII_ID)

    resp = client_factory(usuario).get(
        f"/api/investimentos/{fii.id}/proventos",
        params={"inicio": "2026-07-01", "fim": "2026-07-31"},
    )
    corpo = resp.json()
    assert corpo["total_centavos"] == 1_234  # só o DIVIDEND; BUY (CREDIT) fica de fora
    assert corpo["dy_pct"] == pytest.approx(10.42, abs=0.01)  # 12.34 / 118.40
    assert len(corpo["proventos"]) == 1

    # fora do período → vazio
    junho = client_factory(usuario).get(
        f"/api/investimentos/{fii.id}/proventos",
        params={"inicio": "2026-06-01", "fim": "2026-06-30"},
    )
    assert junho.json()["total_centavos"] == 0

    # isolamento + período inválido
    b = client_factory(usuario_b).get(
        f"/api/investimentos/{fii.id}/proventos",
        params={"inicio": "2026-07-01", "fim": "2026-07-31"},
    )
    assert b.status_code == 404
    invalido = client_factory(usuario).get(
        f"/api/investimentos/{fii.id}/proventos",
        params={"inicio": "2026-07-31", "fim": "2026-07-01"},
    )
    assert invalido.status_code == 422


def test_transacoes_do_investimento_isolamento(db, usuario, conexao, usuario_b, client_factory):
    sincronizar_usuario(db, usuario.id)
    fii = InvestimentoRepository(db, usuario.id).get_by_pluggy_id(FII_ID)

    resp = client_factory(usuario).get(f"/api/investimentos/{fii.id}/transacoes")
    corpo = resp.json()
    assert [t["pluggy_id"] for t in corpo] == ["itx-dividendo", "itx-compra"]  # desc por data

    resp_b = client_factory(usuario_b).get(f"/api/investimentos/{fii.id}/transacoes")
    assert resp_b.status_code == 404


# --- posições agrupadas (tabela) + endpoints de posição (drawer) ----------------------


def test_resumo_traz_posicoes_agrupadas(db, usuario, conexao, usuario_b, client_factory):
    sincronizar_usuario(db, usuario.id)
    conexao.connector_nome = "Nubank"  # após o sync (que grava o connector do Pluggy)
    db.commit()
    posicoes = client_factory(usuario).get("/api/investimentos/resumo").json()["posicoes"]

    # uma linha por ativo agrupado (== quantidade_ativos), ordenado por valor desc (CDB > FII)
    assert len(posicoes) == 2
    assert [p["type"] for p in posicoes] == ["FIXED_INCOME", "EQUITY"]
    assert sum(p["participacao_pct"] for p in posicoes) == pytest.approx(100.0, abs=0.05)
    assert {p["instituicao"] for p in posicoes} == {"Nubank"}  # connector do item

    fii = next(p for p in posicoes if p["type"] == "EQUITY")
    assert fii["chave"] == "rv-GGRC11" and fii["code"] == "GGRC11"
    assert fii["quantidade"] == 1 and fii["preco_medio_centavos"] == 11_900
    assert fii["cotacao_centavos"] == 11_840  # value 118.4 → centavos
    assert fii["valor_centavos"] == 11_840 and fii["resultado_centavos"] == -60
    assert next(p for p in posicoes if p["type"] == "FIXED_INCOME")["chave"].startswith("rf-")

    # sem connector → cai no nome do emissor
    conexao.connector_nome = None
    db.commit()
    depois = client_factory(usuario).get("/api/investimentos/resumo").json()["posicoes"]
    assert next(p for p in depois if p["type"] == "EQUITY")["instituicao"] == "Corretora X"

    # isolamento: B vê carteira vazia
    assert client_factory(usuario_b).get("/api/investimentos/resumo").json()["posicoes"] == []


def test_instituicao_da_posicao_usa_vinculo_manual_da_conta(db, usuario, conexao, client_factory):
    """A instituição vinculada à mão na conta sobrepõe o connector ("meu Pluggy" em dev)."""
    from app.models.conta import Conta
    from app.services import conta as conta_service

    sincronizar_usuario(db, usuario.id)
    conexao.connector_nome = "meu Pluggy"
    db.commit()

    conta = db.scalars(select(Conta).where(Conta.item_id == conexao.id)).first()
    conta_service.vincular_instituicao(db, usuario.id, conta.id, 612, "Nubank", "http://x/nu.png")

    posicoes = client_factory(usuario).get("/api/investimentos/resumo").json()["posicoes"]
    assert {p["instituicao"] for p in posicoes} == {"Nubank"}  # vinculada, não "meu Pluggy"
    assert {p["instituicao_logo_url"] for p in posicoes} == {"http://x/nu.png"}  # logo da vinculada


def test_rv_sem_amount_original_reconstroi_custo_dos_movimentos(db, usuario, conexao):
    """FII sem `amountOriginal` do Pluggy: preço médio e investido vêm do custo médio dos
    movimentos BUY/SELL. Se a qtd reconstruída não cobre a posição, calcula com o parcial e
    marca histórico incompleto (não some — decisão do usuário)."""
    hoje = datetime.now(UTC)
    fii = _criar_investimento(
        db,
        usuario.id,
        conexao.id,
        "rv-recon",
        type="EQUITY",
        subtype="REAL_ESTATE_FUND",
        code="RECON11",
        nome="Fundo Recon",
        quantity=Decimal(5),
        value_unitario=Decimal("110"),
        amount_centavos=55_000,
        saldo_centavos=55_000,
        amount_original_centavos=None,
    )
    for i, (tipo, mov, amt, qt) in enumerate(
        [("BUY", "CREDIT", 40_000, 4), ("BUY", "CREDIT", 20_000, 2), ("SELL", "DEBIT", 11_000, 1)]
    ):
        db.add(
            InvestimentoTransacao(
                investimento_id=fii.id,
                type=tipo,
                movement_type=mov,
                amount_centavos=amt,
                quantity=Decimal(qt),
                date=hoje + timedelta(days=i),
            )
        )
    # FII cuja qtd atual (5) não é coberta pelos movimentos (só 2 compradas) → parcial + aviso.
    mism = _criar_investimento(
        db,
        usuario.id,
        conexao.id,
        "rv-mism",
        type="EQUITY",
        subtype="REAL_ESTATE_FUND",
        code="MISM11",
        nome="Fundo Mismatch",
        quantity=Decimal(5),
        value_unitario=Decimal("100"),
        amount_centavos=50_000,
        saldo_centavos=50_000,
        amount_original_centavos=None,
    )
    db.add(
        InvestimentoTransacao(
            investimento_id=mism.id,
            type="BUY",
            movement_type="CREDIT",
            amount_centavos=20_000,
            quantity=Decimal(2),
            date=hoje,
        )
    )
    db.commit()

    resumo = carteira.resumo_carteira(db, usuario.id)
    por_code = {p.code: p for p in resumo.posicoes}

    recon = por_code["RECON11"]
    assert recon.investido_centavos == 50_000  # 40000+20000 − (60000·1/6) = 50000
    assert recon.preco_medio_centavos == 10_000  # 50000 / 5
    assert recon.resultado_centavos == 5_000  # 55000 − 50000
    assert recon.historico_incompleto is False  # qtd bate → histórico completo na janela

    mism_p = por_code["MISM11"]
    assert mism_p.investido_centavos == 20_000  # só a compra conhecida (2 cotas)
    assert mism_p.preco_medio_centavos == 10_000  # 20000 / 2 (qtd conhecida, não a atual)
    assert mism_p.historico_incompleto is True  # 2 < 5 → há compras antes da janela

    assert resumo.totais.investido_centavos == 70_000  # RECON 50000 + MISM 20000 (parcial)


def test_aportes_manuais_calculo_crud_e_isolamento(db, usuario, conexao, usuario_b, client_factory):
    """Aporte informado à mão entra no custo médio, aparece em /transacoes marcado como manual,
    pode ser editado/excluído e completa o histórico incompleto. Isolado por usuário."""
    # banco só trouxe 11 das 24 cotas (R$1.124,44) — compras antigas ficaram fora da janela.
    fii = _criar_investimento(
        db,
        usuario.id,
        conexao.id,
        "rv-ap",
        type="EQUITY",
        subtype="REAL_ESTATE_FUND",
        code="APORTE11",
        nome="Fundo Aporte",
        quantity=Decimal(24),
        value_unitario=Decimal("100"),
        amount_centavos=241_968,
        saldo_centavos=241_968,
        amount_original_centavos=None,
    )
    db.add(
        InvestimentoTransacao(
            investimento_id=fii.id,
            type="BUY",
            movement_type="CREDIT",
            amount_centavos=112_444,
            quantity=Decimal(11),
            date=datetime(2025, 7, 7, 12, tzinfo=UTC),
        )
    )
    db.commit()

    def posicao():
        db.expire_all()  # chamadas via client usam outra sessão; recarrega p/ ver o commit
        return next(
            p for p in carteira.resumo_carteira(db, usuario.id).posicoes if p.code == "APORTE11"
        )

    # parcial: calcula com o que há (11 cotas) + aviso
    p0 = posicao()
    assert p0.investido_centavos == 112_444
    assert p0.preco_medio_centavos == 10_222  # 112444 / 11
    assert p0.historico_incompleto is True

    cliente = client_factory(usuario)
    # validação: quantidade <= 0 barra
    assert (
        cliente.post(
            f"/api/investimentos/{fii.id}/aportes",
            json={"data": "2024-01-10", "quantidade": 0, "valor_centavos": 100},
        ).status_code
        == 422
    )
    # aporte das 13 cotas faltantes (R$1.235,56) → completa a posição
    r = cliente.post(
        f"/api/investimentos/{fii.id}/aportes",
        json={"data": "2024-03-12", "quantidade": 13, "valor_centavos": 123_556},
    )
    assert r.status_code == 201 and r.json()["manual"] is True and r.json()["type"] == "BUY"
    aporte_id = r.json()["id"]

    p1 = posicao()
    assert p1.historico_incompleto is False  # 11 + 13 = 24 cobre a posição
    assert p1.investido_centavos == 236_000  # 112444 + 123556
    assert p1.preco_medio_centavos == round(236_000 / 24)

    # aparece em /transacoes marcado como manual
    movs = cliente.get(f"/api/investimentos/{fii.id}/transacoes").json()
    manual = next(m for m in movs if m["id"] == aporte_id)
    assert manual["manual"] is True and float(manual["quantity"]) == 13

    # editar muda o cálculo
    assert (
        cliente.patch(
            f"/api/investimentos/aportes/{aporte_id}", json={"valor_centavos": 130_000}
        ).status_code
        == 200
    )
    assert posicao().investido_centavos == 242_444  # 112444 + 130000

    # não mexe em movimento do Pluggy (manual=False) nem em aporte de outro usuário → 404
    mov_pluggy = next(m["id"] for m in movs if not m["manual"])
    assert (
        cliente.patch(
            f"/api/investimentos/aportes/{mov_pluggy}", json={"valor_centavos": 1}
        ).status_code
        == 404
    )
    assert (
        client_factory(usuario_b).delete(f"/api/investimentos/aportes/{aporte_id}").status_code
        == 404
    )

    # excluir volta ao estado parcial + aviso
    assert cliente.delete(f"/api/investimentos/aportes/{aporte_id}").status_code == 204
    p3 = posicao()
    assert p3.investido_centavos == 112_444 and p3.historico_incompleto is True


def test_resync_preserva_aporte_manual(db, usuario, conexao, client_factory):
    """Re-sync não apaga aportes manuais (pluggy_id NULL ficam fora da reconciliação) nem duplica
    os movimentos do Pluggy."""
    sincronizar_usuario(db, usuario.id)
    fii = InvestimentoRepository(db, usuario.id).get_by_pluggy_id(FII_ID)
    aporte_id = (
        client_factory(usuario)
        .post(
            f"/api/investimentos/{fii.id}/aportes",
            json={"data": "2024-02-01", "quantidade": 3, "valor_centavos": 30_000},
        )
        .json()["id"]
    )
    db.expire_all()
    antes = db.scalars(
        select(InvestimentoTransacao).where(InvestimentoTransacao.investimento_id == fii.id)
    ).all()

    sincronizar_usuario(db, usuario.id, forcar=True)
    db.expire_all()
    depois = db.scalars(
        select(InvestimentoTransacao).where(InvestimentoTransacao.investimento_id == fii.id)
    ).all()
    assert db.get(InvestimentoTransacao, aporte_id) is not None  # aporte sobrevive
    assert len(depois) == len(antes)  # movimentos do Pluggy não duplicaram


def test_posicao_transacoes_mescla_e_isolamento(db, usuario, conexao, usuario_b, client_factory):
    a1 = _criar_investimento(db, usuario.id, conexao.id, "pos-a1", amount_centavos=10_000)
    a2 = _criar_investimento(db, usuario.id, conexao.id, "pos-a2", amount_centavos=5_000)
    db.add_all(
        [
            InvestimentoTransacao(
                investimento_id=a1.id,
                pluggy_id="m1",
                type="BUY",
                movement_type="DEBIT",
                amount_centavos=10_000,
                date=datetime(2026, 7, 1, 12, tzinfo=UTC),
            ),
            InvestimentoTransacao(
                investimento_id=a2.id,
                pluggy_id="m2",
                type="BUY",
                movement_type="DEBIT",
                amount_centavos=5_000,
                date=datetime(2026, 7, 3, 12, tzinfo=UTC),
            ),
        ]
    )
    db.commit()

    resp = client_factory(usuario).get(
        "/api/investimentos/posicao/transacoes", params={"ids": [a1.id, a2.id]}
    )
    assert resp.status_code == 200
    assert [t["pluggy_id"] for t in resp.json()] == ["m2", "m1"]  # mescla, desc por data

    # IDOR: qualquer id não-pertencente (inexistente ou de outro usuário) → 404
    misto = client_factory(usuario).get(
        "/api/investimentos/posicao/transacoes", params={"ids": [a1.id, 999_999]}
    )
    assert misto.status_code == 404
    de_b = client_factory(usuario_b).get(
        "/api/investimentos/posicao/transacoes", params={"ids": [a1.id]}
    )
    assert de_b.status_code == 404


def test_posicao_serie_e_proventos(db, usuario, conexao, usuario_b, client_factory):
    inv = _criar_investimento(db, usuario.id, conexao.id, "pos-s", amount_centavos=20_500)
    d1, d2 = date(2026, 7, 1), date(2026, 7, 2)
    _snap(db, inv, d1, 20_000)
    _snap(db, inv, d2, 20_500)
    db.add(
        InvestimentoTransacao(
            investimento_id=inv.id,
            pluggy_id="prov1",
            type="DIVIDEND",
            movement_type="CREDIT",
            amount_centavos=300,
            date=datetime(2026, 7, 2, 12, tzinfo=UTC),
        )
    )
    db.commit()

    serie = client_factory(usuario).get(
        "/api/investimentos/posicao/serie",
        params={"ids": [inv.id], "inicio": "2026-07-01", "fim": "2026-07-02"},
    )
    assert serie.status_code == 200
    assert [p["valor_centavos"] for p in serie.json()["pontos"]] == [20_000, 20_500]

    prov = (
        client_factory(usuario)
        .get(
            "/api/investimentos/posicao/proventos",
            params={"ids": [inv.id], "inicio": "2026-07-01", "fim": "2026-07-31"},
        )
        .json()
    )
    assert prov["total_centavos"] == 300
    assert prov["dy_pct"] == pytest.approx(300 / 20_500 * 100, abs=0.01)

    # período inválido → 422; posição de A pedida por B → 404
    inval = client_factory(usuario).get(
        "/api/investimentos/posicao/serie",
        params={"ids": [inv.id], "inicio": "2026-07-31", "fim": "2026-07-01"},
    )
    assert inval.status_code == 422
    negado = client_factory(usuario_b).get(
        "/api/investimentos/posicao/proventos",
        params={"ids": [inv.id], "inicio": "2026-07-01", "fim": "2026-07-31"},
    )
    assert negado.status_code == 404


# --- ativos: agrupamento de renda fixa (§4.9) -----------------------------------------


def test_agrupa_renda_fixa_por_isin_e_soma_resultado(db, usuario, conexao, client_factory):
    # duas compras do mesmo papel (mesmo ISIN) + um papel diferente
    a1 = _criar_investimento(
        db,
        usuario.id,
        conexao.id,
        "rf-a1",
        isin="BR123",
        nome="Tesouro Selic 2028",
        amount_centavos=10_000,
        amount_original_centavos=9_000,
    )
    a2 = _criar_investimento(
        db,
        usuario.id,
        conexao.id,
        "rf-a2",
        isin="BR123",
        nome="Tesouro Selic 2028",
        amount_centavos=5_000,
        amount_original_centavos=4_000,
    )
    b = _criar_investimento(
        db,
        usuario.id,
        conexao.id,
        "rf-b",
        isin="BR999",
        nome="CDB Outro",
        amount_centavos=2_000,
        amount_original_centavos=2_000,
    )

    agrupar_renda_fixa(db, usuario.id)
    for inv in (a1, a2, b):
        db.refresh(inv)
    assert a1.ativo_id is not None and a1.ativo_id == a2.ativo_id  # mesmo ISIN → mesmo ativo
    assert b.ativo_id is not None and b.ativo_id != a1.ativo_id  # ISIN diferente → outro ativo
    assert len(db.scalars(select(Ativo)).all()) == 2

    # resultado do ativo = soma das partes (10000−9000)+(5000−4000)=2000; investido 13000
    resumo = client_factory(usuario).get("/api/investimentos/resumo").json()
    # 3 compras (a1,a2 mesmo ISIN + b) → 2 ativos distintos (não 3 posições)
    assert resumo["totais"]["quantidade_ativos"] == 2
    juntos = next(a for a in resumo["renda_fixa"] if a["ativo_id"] == a1.ativo_id)
    assert set(juntos["investimento_ids"]) == {a1.id, a2.id}
    assert juntos["investido_centavos"] == 13_000
    assert juntos["valor_centavos"] == 15_000
    assert juntos["resultado_centavos"] == 2_000
    assert len(juntos["posicoes"]) == 2

    # idempotente + não sobrescreve ajuste manual
    manual = Ativo(usuario_id=usuario.id, nome="Meu CDB")
    db.add(manual)
    db.commit()
    db.refresh(manual)
    b.ativo_id = manual.id
    db.commit()
    agrupar_renda_fixa(db, usuario.id)
    db.refresh(b)
    assert b.ativo_id == manual.id


def test_resync_preserva_ativo_id(db, usuario, conexao):
    sincronizar_usuario(db, usuario.id)
    repo = InvestimentoRepository(db, usuario.id)
    cdb = repo.get_by_pluggy_id(CDB_ID)
    assert cdb.ativo_id is not None  # agrupador criou um ativo p/ a renda fixa

    manual = Ativo(usuario_id=usuario.id, nome="Meu CDB")
    db.add(manual)
    db.commit()
    db.refresh(manual)
    repo.update(cdb, ativo_id=manual.id)

    sincronizar_usuario(db, usuario.id, forcar=True)
    db.refresh(cdb)
    # upsert (pop ativo_id) + agrupador (só preenche nulo) → ajuste manual sobrevive
    assert cdb.ativo_id == manual.id


def test_patch_investimento_vincula_ativo_e_isolamento(
    db, usuario, conexao, usuario_b, client_factory
):
    sincronizar_usuario(db, usuario.id)
    cdb = InvestimentoRepository(db, usuario.id).get_by_pluggy_id(CDB_ID)

    criado = client_factory(usuario).post("/api/ativos", json={"nome": "Reserva"})
    assert criado.status_code == 201
    ativo_id = criado.json()["id"]

    vinc = client_factory(usuario).patch(
        f"/api/investimentos/{cdb.id}", json={"ativo_id": ativo_id}
    )
    assert vinc.status_code == 200 and vinc.json()["ativo_id"] == ativo_id

    ren = client_factory(usuario).patch(f"/api/ativos/{ativo_id}", json={"nome": "Reserva RF"})
    assert ren.status_code == 200 and ren.json()["nome"] == "Reserva RF"

    # vincular ao ativo de OUTRO usuário → 404 (S3)
    ativo_b = client_factory(usuario_b).post("/api/ativos", json={"nome": "De B"}).json()["id"]
    neg = client_factory(usuario).patch(f"/api/investimentos/{cdb.id}", json={"ativo_id": ativo_b})
    assert neg.status_code == 404


def test_proventos_fii_total_isento(db, usuario, conexao, client_factory):
    sincronizar_usuario(db, usuario.id)
    fii = InvestimentoRepository(db, usuario.id).get_by_pluggy_id(FII_ID)
    corpo = (
        client_factory(usuario)
        .get(
            f"/api/investimentos/{fii.id}/proventos",
            params={"inicio": "2026-07-01", "fim": "2026-07-31"},
        )
        .json()
    )
    assert corpo["total_centavos"] == 1_234
    assert corpo["total_isento_centavos"] == 1_234  # DIVIDEND/INTEREST são isentos de IR


# --- série da carteira ----------------------------------------------------------------


def _criar_investimento(db, usuario_id, item_id, pluggy_id, **campos) -> Investimento:
    base = {"type": "FIXED_INCOME", "saldo_centavos": 0}
    inv = Investimento(
        usuario_id=usuario_id, item_id=item_id, pluggy_investment_id=pluggy_id, **(base | campos)
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return inv


def _snap(db, inv: Investimento, dia: date, valor: int) -> None:
    db.add(
        InvestimentoSaldoDiario(
            usuario_id=inv.usuario_id, investimento_id=inv.id, data=dia, valor_centavos=valor
        )
    )
    db.commit()


def test_serie_twr_com_fluxo_nao_conta_aporte_como_ganho(db, usuario, conexao):
    inv = _criar_investimento(db, usuario.id, conexao.id, "inv-serie")
    d1, d2, d3 = date(2026, 7, 1), date(2026, 7, 2), date(2026, 7, 3)
    _snap(db, inv, d1, 10_000)
    _snap(db, inv, d2, 10_100)  # +1% real
    _snap(db, inv, d3, 20_300)  # aporte de 10_000 + ~1.98% real
    db.add(
        InvestimentoTransacao(
            investimento_id=inv.id,
            pluggy_id="mov-aporte",
            type="BUY",
            movement_type="CREDIT",
            amount_centavos=10_000,
            trade_date=datetime(2026, 7, 3, 12, tzinfo=UTC),
        )
    )
    db.commit()

    serie = carteira.serie_carteira(db, usuario.id, d1, d3)
    assert [p.valor_centavos for p in serie.pontos] == [10_000, 10_100, 20_300]
    assert serie.pontos[0].acumulado_pct == 0
    assert serie.pontos[1].acumulado_pct == pytest.approx(1.0, abs=0.001)
    # sem o ajuste de fluxo o acumulado saltaria p/ ~103%; TWR: (1.01 × 1.0198) − 1
    assert serie.pontos[2].acumulado_pct == pytest.approx(3.0, abs=0.01)


def test_serie_recorte_filtra_e_forward_fill(db, usuario, conexao):
    rf = _criar_investimento(db, usuario.id, conexao.id, "inv-rf", type="FIXED_INCOME")
    rv = _criar_investimento(db, usuario.id, conexao.id, "inv-rv", type="ETF")
    d1, d3 = date(2026, 7, 1), date(2026, 7, 3)
    _snap(db, rf, d1, 50_000)
    _snap(db, rv, d1, 30_000)
    _snap(db, rf, d3, 51_000)  # d2 sem snapshot → forward-fill

    todos = carteira.serie_carteira(db, usuario.id, d1, d3)
    assert [p.valor_centavos for p in todos.pontos] == [80_000, 80_000, 81_000]

    so_rf = carteira.serie_carteira(db, usuario.id, d1, d3, recorte="renda_fixa")
    assert [p.valor_centavos for p in so_rf.pontos] == [50_000, 50_000, 51_000]

    por_subtype = carteira.serie_carteira(db, usuario.id, d1, d3, subtype="CDB")
    assert por_subtype.pontos == []  # nenhum investimento com esse subtype

    # isolamento: outro usuário não enxerga a série
    outro = Usuario(nome="B", email="b-serie@mango.test")
    db.add(outro)
    db.commit()
    assert carteira.serie_carteira(db, outro.id, d1, d3).pontos == []


def test_serie_reconstroi_renda_variavel_antes_do_snapshot(db, usuario, conexao, monkeypatch):
    rv = _criar_investimento(
        db, usuario.id, conexao.id, "inv-acao", type="EQUITY", code="XPTO3", quantity=Decimal(2)
    )
    d1, d2, d3 = date(2026, 7, 1), date(2026, 7, 2), date(2026, 7, 3)
    _snap(db, rv, d3, 20_600)  # snapshot só no fim; d1–d2 vêm da reconstrução
    # compra de 1 cota em d2 → em d1 a posição era 1
    db.add(
        InvestimentoTransacao(
            investimento_id=rv.id,
            pluggy_id="mov-compra-xpto",
            type="BUY",
            movement_type="CREDIT",
            amount_centavos=10_100,
            quantity=Decimal(1),
            trade_date=datetime(2026, 7, 2, 12, tzinfo=UTC),
        )
    )
    db.commit()

    monkeypatch.setattr(settings, "brapi_token", "tok")
    precos = {d1: Decimal(100), d2: Decimal(101)}
    monkeypatch.setattr(
        carteira.indicadores, "precos_historicos", lambda ticker, ini, fim, token=None: precos
    )

    serie = carteira.serie_carteira(db, usuario.id, d1, d3, recorte="renda_variavel")
    # d1: 100 × 1 cota; d2: 101 × 2 cotas; d3: snapshot (verdade)
    assert [(p.data, p.valor_centavos) for p in serie.pontos] == [
        (d1, 10_000),
        (d2, 20_200),
        (d3, 20_600),
    ]
    # TWR: d2 tem fluxo de 10_100 → r2 = (20200−10100−10000)/10000 = 1%; r3 ≈ 1.98%
    assert serie.pontos[2].acumulado_pct == pytest.approx(3.0, abs=0.01)

    # sem token → sem reconstrução: série começa no snapshot
    monkeypatch.setattr(settings, "brapi_token", "")
    sem_token = carteira.serie_carteira(db, usuario.id, d1, d3, recorte="renda_variavel")
    assert [p.data for p in sem_token.pontos] == [d3]


def test_serie_posicao_reconstroi_renda_fixa_multiplas_compras(db, usuario, conexao, monkeypatch):
    # compras em d1 e d3 (mesmo título, lotes distintos); d2 é dia sem compra; snapshot só em d5.
    d1, d2, d3, d4, d5 = (date(2026, 7, n) for n in (1, 2, 3, 4, 5))
    dt = lambda d: datetime(d.year, d.month, d.day, 12, tzinfo=UTC)  # noqa: E731
    lotes = [("a", d1, 10_000, 10_150), ("b", d3, 5_000, 5_050)]  # data, aplicado, bruto atual
    invs = []
    for pid, compra, aplicado, bruto in lotes:
        inv = _criar_investimento(
            db,
            usuario.id,
            conexao.id,
            f"inv-td-{pid}",
            subtype="TREASURY",
            rate_type="SELIC",
            purchase_date=dt(compra),
            amount_original_centavos=aplicado,
            amount_centavos=bruto,
        )
        _snap(db, inv, d5, bruto)  # d1–d4 vêm da reconstrução, d5 é a verdade
        invs.append(inv)
    ids = [i.id for i in invs]

    # SELIC realizada (acumulada desde a 1ª compra), forward-fill p/ os dias omitidos.
    def fake_serie(codigo, ini, fim, token=None):
        assert codigo == "selic"
        return [(d1, 0.0), (d3, 0.1), (d4, 0.15), (d5, 0.2)]

    monkeypatch.setattr(carteira.indicadores, "serie", fake_serie)

    serie = carteira.serie_posicao(db, usuario.id, ids, d1, d5)
    assert [p.data for p in serie.pontos] == [d1, d2, d3, d4, d5]
    assert serie.reconstruido_ate == d4  # dias até o anterior ao snapshot são estimados
    assert serie.pontos[-1].valor_centavos == 15_200  # d5: snapshot real (soma dos lotes)
    # aplicado sobe a cada compra (via purchase_date + amount_original), não conta rendimento.
    assert [p.investido_centavos for p in serie.pontos] == [10_000, 10_000, 15_000, 15_000, 15_000]
    # bruto: cada lote cresce pela SELIC de sua data, calibrado p/ terminar no bruto atual (15_200).
    k = 15_200 / (10_000 * (1.002 / 1.0) + 5_000 * (1.002 / 1.001))
    assert serie.pontos[0].valor_centavos == pytest.approx(10_000 * k, abs=1)  # d1: só o 1º lote
    assert serie.pontos[2].valor_centavos == pytest.approx(15_010 * k, abs=1)  # d3: 1º cresc. + 2º

    # Sem purchase_date → sem aportes p/ reconstruir: começa no snapshot.
    for inv in invs:
        inv.purchase_date = None
    db.commit()
    parcial = carteira.serie_posicao(db, usuario.id, ids, d1, d5)
    assert [p.data for p in parcial.pontos] == [d5]
    assert parcial.reconstruido_ate is None


def test_serie_expoe_investido_acumulado(db, usuario, conexao):
    inv = _criar_investimento(
        db, usuario.id, conexao.id, "inv-inv", amount_original_centavos=20_000
    )
    d1, d2 = date(2026, 7, 1), date(2026, 7, 2)
    _snap(db, inv, d1, 10_000)
    _snap(db, inv, d2, 20_500)  # aporte de 10_000 + rendimento
    db.add(
        InvestimentoTransacao(
            investimento_id=inv.id,
            pluggy_id="mov-ap",
            type="BUY",
            movement_type="CREDIT",
            amount_centavos=10_000,
            trade_date=datetime(2026, 7, 2, 12, tzinfo=UTC),
        )
    )
    db.commit()

    serie = carteira.serie_carteira(db, usuario.id, d1, d2)
    # investido termina no total investido atual (20_000) e recua pelos fluxos: d1=10_000, d2=20_000
    assert [p.investido_centavos for p in serie.pontos] == [10_000, 20_000]


def test_serie_posicao_renda_fixa_resgate_nunca_negativo(db, usuario, conexao, monkeypatch):
    # aporte de 10_000 em d1 que rende 100% (dobra) até d3; resgate (SELL) de 15_000 em d3 — maior
    # que o principal. Rateio proporcional: no d3 o bruto é ~20_000, saca 75% → bruto 5_000,
    # aplicado 2_500. Nem o aplicado nem o bruto podem ficar negativos.
    d1, d2, d3, d4, d5 = (date(2026, 7, n) for n in (1, 2, 3, 4, 5))
    dt = lambda d: datetime(d.year, d.month, d.day, 12, tzinfo=UTC)  # noqa: E731
    inv = _criar_investimento(
        db,
        usuario.id,
        conexao.id,
        "inv-td-resgate",
        subtype="TREASURY",
        rate_type="SELIC",
        purchase_date=dt(d1),
        amount_original_centavos=10_000,
        amount_centavos=5_000,
    )
    _snap(db, inv, d5, 5_000)
    db.add(
        InvestimentoTransacao(
            investimento_id=inv.id,
            pluggy_id="mov-resgate",
            type="SELL",
            movement_type="DEBIT",
            amount_centavos=15_000,  # armazenado positivo; o sinal vem do type
            trade_date=dt(d3),
        )
    )
    db.commit()

    # SELIC realizada: 0% até d1, +100% acumulado em d3 (dobra o bruto antes do resgate).
    monkeypatch.setattr(
        carteira.indicadores,
        "serie",
        lambda c, i, f, token=None: [(d1, 0.0), (d3, 100.0), (d5, 100.0)],
    )

    serie = carteira.serie_posicao(db, usuario.id, [inv.id], d1, d5)
    aplicado = [p.investido_centavos for p in serie.pontos]
    bruto = [p.valor_centavos for p in serie.pontos]
    assert aplicado == [10_000, 10_000, 2_500, 2_500, 2_500]  # cai no resgate, nunca negativo
    assert bruto == [10_000, 10_000, 5_000, 5_000, 5_000]  # d3 saca 15_000 de ~20_000; d5=snapshot
    assert all(v >= 0 for v in aplicado + bruto)


# --- visão geral (dashboard) ----------------------------------------------------------


def test_visao_geral_dashboard(db, usuario, conexao, usuario_b, client_factory, monkeypatch):
    hoje = datetime.now(carteira.SP).date()
    dia_base = hoje - timedelta(days=180)

    cdb = _criar_investimento(
        db,
        usuario.id,
        conexao.id,
        "vg-cdb",
        type="FIXED_INCOME",
        nome="CDB Banco XP",
        amount_centavos=100_000,
        amount_original_centavos=90_000,
    )
    fii = _criar_investimento(
        db,
        usuario.id,
        conexao.id,
        "vg-fii",
        type="EQUITY",
        subtype="REAL_ESTATE_FUND",
        code="HGLG11",
        nome="CSHG Logística",
        quantity=Decimal(10),
        amount_centavos=50_000,
        amount_original_centavos=45_000,
    )
    for inv, v0, v1 in ((cdb, 90_000, 100_000), (fii, 45_000, 50_000)):
        _snap(db, inv, dia_base, v0)
        _snap(db, inv, hoje, v1)
    db.add(
        InvestimentoTransacao(
            investimento_id=fii.id,
            pluggy_id="vg-div",
            type="DIVIDEND",
            movement_type="CREDIT",
            amount_centavos=1_230,
            date=datetime.combine(hoje, time(12), tzinfo=UTC),
        )
    )
    db.commit()

    # CDI mockado (evita rede); série da carteira vem dos snapshots.
    monkeypatch.setattr(carteira.indicadores, "serie", lambda c, i, f, token=None: [(f, 5.0)])

    corpo = client_factory(usuario).get("/api/investimentos/visao-geral").json()
    assert corpo["dividendos_mes_centavos"] == 1_230
    assert corpo["rentabilidade_12m_pct"] == pytest.approx(11.11, abs=0.2)  # 150k/135k − 1
    assert corpo["vs_cdi_pp"] == round(corpo["rentabilidade_12m_pct"] - 5.0, 2)

    # isolamento: B tem carteira vazia
    vazio = client_factory(usuario_b).get("/api/investimentos/visao-geral").json()
    assert vazio["dividendos_mes_centavos"] == 0 and vazio["rentabilidade_12m_pct"] is None
