"""Abas Receitas/Despesas do dashboard (`montar_analise`) e a regra do estorno de cartão."""

from datetime import date

from sqlalchemy.orm import Session

from app.models.categoria import Categoria
from app.models.orcamento import Orcamento, OrcamentoMensal
from app.models.transacao import TransacaoPagamento
from app.repositories.transacao import TransacaoRepository
from app.services.dashboard import (
    lancamentos_da_analise,
    montar_analise,
    montar_dashboard,
    montar_series,
    periodo_anterior,
)
from app.services.orcamento_consumo import consumo_do_mes, transacoes_do_item
from tests.test_dashboard import _contas, _em, _tx, _usuario

FEV = (date(2026, 2, 1), date(2026, 2, 28))


def _cats(db: Session) -> None:
    db.add_all(
        [
            Categoria(pluggy_id="01000000", description="Renda"),
            Categoria(pluggy_id="01010000", description="Salario", parent_id="01000000"),
            Categoria(pluggy_id="10000000", description="Supermercado"),
            Categoria(pluggy_id="17000000", description="Moradia"),
        ]
    )
    db.commit()


def test_periodo_anterior():
    assert periodo_anterior(date(2026, 11, 1), date(2026, 11, 23)) == (
        date(2026, 10, 1),
        date(2026, 10, 23),
    )
    assert periodo_anterior(date(2026, 3, 1), date(2026, 3, 31)) == (
        date(2026, 2, 1),
        date(2026, 2, 28),
    )
    assert periodo_anterior(date(2026, 8, 24), date(2026, 8, 30)) == (
        date(2026, 8, 17),
        date(2026, 8, 23),
    )


def test_estorno_de_cartao_abate_despesa_e_nao_e_receita(db: Session):
    u = _usuario(db, "estorno@mango.test")
    _cats(db)
    bank, credit = _contas(db, u.id)
    repo = TransacaoRepository(db, u.id)
    _tx(repo, credit, "compra", -10_000, cat="10000000", quando=_em(2026, 2, 3))
    _tx(repo, credit, "estorno", 4_000, cat="10000000", quando=_em(2026, 2, 5))
    _tx(repo, credit, "cashback", 500, cat="01010000", quando=_em(2026, 2, 6))  # Renda → receita
    _tx(repo, bank, "salario", 800_000, cat="01010000", quando=_em(2026, 2, 5))

    d = montar_dashboard(db, u.id, *FEV)
    assert d.saidas_centavos == 6_000
    assert d.entradas_centavos == 800_500
    assert {g.categoria_id: g.total_centavos for g in d.gasto_por_categoria} == {"10000000": 6_000}

    # Orçamento: realizado e drill-down usam a mesma regra (lista soma o realizado).
    orc = Orcamento(
        usuario_id=u.id,
        categoria_id="10000000",
        tipo="despesa",
        limite_padrao_centavos=50_000,
        ordem=0,
    )
    db.add(orc)
    db.commit()
    db.add(
        OrcamentoMensal(
            usuario_id=u.id,
            orcamento_id=orc.id,
            categoria_id="10000000",
            tipo="despesa",
            ano=2026,
            mes=2,
            limite_centavos=50_000,
        )
    )
    db.commit()
    item = consumo_do_mes(db, u.id, 2026, 2).itens[0]
    assert item.realizado_centavos == 6_000
    txs, _ = transacoes_do_item(db, u.id, 2026, 2, "despesa", "10000000")
    assert {t.pluggy_transaction_id for t in txs} == {"compra", "estorno"}
    receitas, _ = transacoes_do_item(db, u.id, 2026, 2, "receita", "10000000")
    assert receitas == []


def test_analise_despesa_reconcilia_e_quebra(db: Session):
    u = _usuario(db, "analise@mango.test")
    _cats(db)
    bank, credit = _contas(db, u.id)
    repo = TransacaoRepository(db, u.id)
    # Fevereiro/2026: 4 segundas (2, 9, 16, 23).
    for i, dia in enumerate([2, 9, 16]):
        _tx(repo, credit, f"mercado{i}", -10_000, cat="10000000", quando=_em(2026, 2, dia))
    aluguel = _tx(repo, bank, "aluguel", -150_000, cat="17000000", quando=_em(2026, 2, 5))
    aluguel.operation_type = "PIX"
    for i in range(6):  # contrapartes pequenas → "Outros"
        t = _tx(repo, bank, f"loja{i}", -1_000 - i, cat="10000000", quando=_em(2026, 2, 10))
        t.merchant_nome = f"Loja {i}"
    db.add(TransacaoPagamento(transacao_id=aluguel.id, metodo="PIX", receiver_nome="Imobiliária X"))
    _tx(repo, bank, "jan", -7_000, cat="10000000", quando=_em(2026, 1, 10))  # período anterior
    _tx(repo, bank, "pgto", -99_000, eh=True, quando=_em(2026, 2, 10))  # transferência → fora
    db.commit()

    a = montar_analise(db, u.id, "despesa", *FEV)
    dash = montar_dashboard(db, u.id, *FEV)
    assert a.total_centavos == dash.saidas_centavos == 30_000 + 150_000 + 6_015
    assert a.anterior_centavos == 7_000
    assert (a.anterior_inicio, a.anterior_fim) == (date(2026, 1, 1), date(2026, 1, 28))
    assert sorted(a.por_categoria, key=lambda g: g.categoria_id or "") == sorted(
        dash.gasto_por_categoria, key=lambda g: g.categoria_id or ""
    )

    # Top 5 contrapartes + "Outros"; a do aluguel vem do recebedor do Pix.
    assert a.contrapartes[0].nome == "Imobiliária X"
    assert len(a.contrapartes) == 5
    assert a.outras_contrapartes_quantidade == 3  # 8 contrapartes (sem nome = 1)
    assert sum(c.total_centavos for c in a.contrapartes) + a.outras_contrapartes_centavos == (
        a.total_centavos
    )

    meios = {m.meio: m.total_centavos for m in a.meios}
    assert meios == {"Pix": 150_000, "Cartão de crédito": 30_000, "Outros": 6_015}
    assert sum(meios.values()) == a.total_centavos

    seg = a.dias_semana[0]
    assert (seg.total_centavos, seg.ocorrencias) == (30_000, 4)
    assert sum(d.ocorrencias for d in a.dias_semana) == 28

    assert a.acumulado[-1].atual_centavos == a.total_centavos
    assert a.acumulado[9].anterior_centavos == 7_000  # 10/jan ↔ índice 9
    assert a.acumulado[0].esperado_centavos is None  # sem orçamento

    # Drill-down soma o pedaço do gráfico.
    chave = a.contrapartes[0].chave
    lista = lancamentos_da_analise(db, u.id, "despesa", *FEV, contraparte=chave)
    assert sum(x.valor for x in lista) == a.contrapartes[0].total_centavos
    cartao = lancamentos_da_analise(db, u.id, "despesa", *FEV, meio="Cartão de crédito")
    assert sum(x.valor for x in cartao) == 30_000


def test_analise_receita_previsto_pelo_orcamento(db: Session):
    u = _usuario(db, "previsto@mango.test")
    _cats(db)
    bank, _ = _contas(db, u.id)
    repo = TransacaoRepository(db, u.id)
    _tx(repo, bank, "sal", 900_000, cat="01010000", quando=_em(2026, 2, 5))
    _tx(repo, bank, "extra", 50_000, quando=_em(2026, 2, 20))
    # Orçamento de receita: pai (Renda) + filho (Salário) → só a raiz soma no previsto.
    for cat, lim in [("01000000", 1_000_000), ("01010000", 800_000)]:
        o = Orcamento(
            usuario_id=u.id, categoria_id=cat, tipo="receita", limite_padrao_centavos=lim, ordem=0
        )
        db.add(o)
        db.commit()
        db.add(
            OrcamentoMensal(
                usuario_id=u.id,
                orcamento_id=o.id,
                categoria_id=cat,
                tipo="receita",
                ano=2026,
                mes=2,
                limite_centavos=lim,
            )
        )
    db.commit()

    a = montar_analise(db, u.id, "receita", date(2026, 2, 10), date(2026, 2, 28))
    assert a.total_centavos == 50_000  # só o que caiu no período
    # Previsto × realizado olha o mês inteiro.
    assert [(p.mes, p.previsto_centavos, p.realizado_centavos) for p in a.previsto] == [
        ("2026-02", 1_000_000, 950_000)
    ]
    assert a.acumulado[-1].esperado_centavos == round(1_000_000 * 19 / 28)
    assert a.meios == [] or all(m.meio != "Cartão de crédito" for m in a.meios)


def test_analise_isola_usuario(db: Session):
    a_ = _usuario(db, "iso-a@mango.test")
    b_ = _usuario(db, "iso-b@mango.test")
    bank_a, _ = _contas(db, a_.id)
    bank_b, _ = _contas(db, b_.id)
    _tx(TransacaoRepository(db, a_.id), bank_a, "a", -1_000, quando=_em(2026, 2, 3))
    _tx(TransacaoRepository(db, b_.id), bank_b, "b", -99_000, quando=_em(2026, 2, 3))
    assert montar_analise(db, a_.id, "despesa", *FEV).total_centavos == 1_000


def test_series_anual(db: Session):
    u = _usuario(db, "anual@mango.test")
    bank, _ = _contas(db, u.id)
    repo = TransacaoRepository(db, u.id)
    _tx(repo, bank, "x", -1_000, quando=_em(2025, 12, 31))
    _tx(repo, bank, "y", -2_000, quando=_em(2026, 1, 1))
    s = montar_series(db, u.id, date(2025, 6, 1), date(2026, 2, 1), "anual")
    assert [(b.inicio, b.saidas_centavos) for b in s.buckets] == [
        (date(2025, 1, 1), 1_000),
        (date(2026, 1, 1), 2_000),
    ]


def test_rota_analise_valida_periodo(client_factory, db: Session):
    u = _usuario(db, "rota@mango.test")
    c = client_factory(u)
    r = c.get("/api/dashboard/analise", params={"natureza": "despesa"})
    assert r.status_code == 200
    r = c.get(
        "/api/dashboard/analise",
        params={"natureza": "despesa", "inicio": "2026-02-10", "fim": "2026-02-01"},
    )
    assert r.status_code == 422
    r = c.get("/api/dashboard/analise", params={"natureza": "investimento"})
    assert r.status_code == 422
    r = c.get("/api/dashboard/analise/transacoes", params={"natureza": "receita"})
    assert r.json() == {"items": [], "total": 0}
