"""Agregações do dashboard (§4.10): exclusão de transferências, corte de período, isolamento."""

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.models.cartao_fatura import Cartao, Fatura
from app.models.categoria import Categoria
from app.models.pluggy import CredencialPluggy, Instituicao, ItemPluggy
from app.models.usuario import Usuario
from app.repositories.conta import ContaRepository
from app.repositories.transacao import TransacaoRepository
from app.services.dashboard import montar_dashboard, montar_series, resumo_faturas
from app.services.periodo import mes_corrente


def _usuario(db: Session, email: str) -> Usuario:
    u = Usuario(nome="U", email=email)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _contas(db: Session, usuario_id: int):
    inst = Instituicao(usuario_id=usuario_id, nome="B", pluggy_connector_id=1)
    cred = CredencialPluggy(usuario_id=usuario_id, client_id_cifrado="c", client_secret_cifrado="s")
    db.add_all([inst, cred])
    db.commit()
    db.refresh(inst)
    db.refresh(cred)
    item = ItemPluggy(usuario_id=usuario_id, credencial_id=cred.id, pluggy_item_id="i")
    db.add(item)
    db.commit()
    db.refresh(item)
    repo = ContaRepository(db, usuario_id)
    base = {"item_id": item.id, "instituicao_id": inst.id, "subtype": None, "currency_code": "BRL"}
    bank = repo.upsert_by_pluggy_id(f"b{usuario_id}", type="BANK", saldo_centavos=100_000, **base)
    credit = repo.upsert_by_pluggy_id(
        f"c{usuario_id}", type="CREDIT", saldo_centavos=-5_000, **base
    )
    return bank, credit


def _tx(repo, conta, pid, amount, *, cat=None, eh=False, quando=None, acc=None, moeda="BRL"):
    return repo.create(
        conta_id=conta.id,
        pluggy_transaction_id=pid,
        date=quando or datetime.now(UTC),
        amount_centavos=amount,
        amount_in_account_currency_centavos=acc,  # valor na moeda da conta (compra internacional)
        currency_code=moeda,
        type="CREDIT" if amount > 0 else "DEBIT",
        status="POSTED",
        categoria_pluggy_id=cat,
        eh_transferencia=eh,
    )


@pytest.fixture
def usuario(db: Session) -> Usuario:
    return _usuario(db, "dash@mango.test")


def test_dashboard_exclui_transferencias_e_soma_saldo_bank(db, usuario):
    for cid in ["07010000", "05100000"]:
        db.add(Categoria(pluggy_id=cid, description=cid))
    bank, _credit = _contas(db, usuario.id)
    repo = TransacaoRepository(db, usuario.id)
    _tx(repo, bank, "sal", 850_000)
    _tx(repo, bank, "vivo", -12_000, cat="07010000")
    _tx(repo, bank, "pgto-fatura", -30_000, cat="05100000", eh=True)  # transferência → fora
    _tx(repo, bank, "antigo", 500_000, quando=datetime(2000, 1, 1, tzinfo=UTC))  # fora do período

    d = montar_dashboard(db, usuario.id, *mes_corrente())

    assert d.entradas_centavos == 850_000  # 'antigo' fora do período
    assert d.saidas_centavos == 12_000  # pagamento de fatura excluído (§4.2)
    assert d.resultado_centavos == 838_000
    assert d.saldo_total_centavos == 100_000  # só contas BANK
    assert {g.categoria_id: g.total_centavos for g in d.gasto_por_categoria} == {"07010000": 12_000}
    assert d.nao_revisadas == 4  # contagem é global (todas ainda não revisadas)


def test_dashboard_usa_valor_convertido_em_compra_internacional(db, usuario):
    """Compra internacional: soma o valor convertido em reais (`amountInAccountCurrency`), não o
    valor na moeda estrangeira. Ex.: Anthropic US$ 21,67 → R$ 117,88 na fatura."""
    db.add(Categoria(pluggy_id="07010000", description="c"))
    bank, _ = _contas(db, usuario.id)
    repo = TransacaoRepository(db, usuario.id)
    _tx(repo, bank, "anthropic", -2_167, cat="07010000", acc=-11_788, moeda="USD")

    d = montar_dashboard(db, usuario.id, *mes_corrente())
    assert d.saidas_centavos == 11_788  # BRL convertido, não 2_167 (USD cru)
    assert {g.categoria_id: g.total_centavos for g in d.gasto_por_categoria} == {"07010000": 11_788}


def test_dashboard_nao_enxerga_outro_usuario(db, usuario):
    """Isolamento (S3): as somas de A nunca incluem transações de B."""
    outro = _usuario(db, "outro@mango.test")
    bank_a, _ = _contas(db, usuario.id)
    bank_b, _ = _contas(db, outro.id)
    _tx(TransacaoRepository(db, usuario.id), bank_a, "a1", 100_000)
    _tx(TransacaoRepository(db, outro.id), bank_b, "b1", 999_000)

    d = montar_dashboard(db, usuario.id, *mes_corrente())
    assert d.entradas_centavos == 100_000  # sem os 999_000 de B
    assert d.nao_revisadas == 1


# 12:00 UTC = 09:00 SP → mesmo dia civil, evita ambiguidade de fuso nos buckets.
def _em(y, m, d):
    return datetime(y, m, d, 12, tzinfo=UTC)


def test_series_semanal_reconcilia_com_kpis_e_preenche_lacunas(db, usuario):
    db.add(Categoria(pluggy_id="07010000", description="c"))
    bank, _ = _contas(db, usuario.id)
    repo = TransacaoRepository(db, usuario.id)
    _tx(repo, bank, "e1", 850_000, quando=_em(2026, 6, 2))
    _tx(repo, bank, "s1", -12_000, cat="07010000", quando=_em(2026, 6, 3))
    _tx(repo, bank, "e2", 20_000, quando=_em(2026, 6, 17))  # semana diferente
    _tx(repo, bank, "transf", -30_000, eh=True, quando=_em(2026, 6, 4))  # excluída

    inicio, fim = date(2026, 6, 1), date(2026, 6, 30)
    serie = montar_series(db, usuario.id, inicio, fim, "semanal")
    d = montar_dashboard(db, usuario.id, inicio, fim)

    # a soma dos buckets bate com os KPIs do mesmo período (invariante central)
    assert sum(b.entradas_centavos for b in serie.buckets) == d.entradas_centavos == 870_000
    assert sum(b.saidas_centavos for b in serie.buckets) == d.saidas_centavos == 12_000

    cat_total: dict[str | None, int] = {}
    for b in serie.buckets:
        for g in b.por_categoria:
            cat_total[g.categoria_id] = cat_total.get(g.categoria_id, 0) + g.total_centavos
    assert cat_total == {"07010000": 12_000}  # transferência fora, categoria agregada

    # gap-filling: buckets contíguos de segunda em segunda cobrindo o período
    inicios = [b.inicio for b in serie.buckets]
    assert inicios == sorted(inicios) and len(inicios) >= 4
    assert all(b - a == timedelta(days=7) for a, b in zip(inicios, inicios[1:], strict=False))


def test_series_mensal_agrupa_por_mes(db, usuario):
    bank, _ = _contas(db, usuario.id)
    repo = TransacaoRepository(db, usuario.id)
    _tx(repo, bank, "m1", 100_000, quando=_em(2026, 5, 10))
    _tx(repo, bank, "m2", 200_000, quando=_em(2026, 7, 10))

    serie = montar_series(db, usuario.id, date(2026, 5, 1), date(2026, 7, 31), "mensal")
    por_mes = {b.inicio: b.entradas_centavos for b in serie.buckets}
    assert por_mes == {date(2026, 5, 1): 100_000, date(2026, 6, 1): 0, date(2026, 7, 1): 200_000}


def test_series_diaria_agrupa_por_dia(db, usuario):
    bank, _ = _contas(db, usuario.id)
    repo = TransacaoRepository(db, usuario.id)
    _tx(repo, bank, "d1", 100_000, quando=_em(2026, 6, 10))
    _tx(repo, bank, "d2", 200_000, quando=_em(2026, 6, 12))  # dia 11 fica vazio no meio

    serie = montar_series(db, usuario.id, date(2026, 6, 10), date(2026, 6, 12), "diaria")
    por_dia = {b.inicio: b.entradas_centavos for b in serie.buckets}
    assert por_dia == {
        date(2026, 6, 10): 100_000,
        date(2026, 6, 11): 0,
        date(2026, 6, 12): 200_000,
    }


def _fatura(db, usuario_id, cartao, pid, total, quando) -> Fatura:
    f = Fatura(
        usuario_id=usuario_id,
        cartao_id=cartao.id,
        pluggy_bill_id=pid,
        due_date=quando,
        total_amount_centavos=total,
    )
    db.add(f)
    db.commit()
    db.refresh(f)
    return f


def test_resumo_faturas_ordena_e_quebra_por_categoria(db, usuario):
    for cid in ["07010000", "05100000"]:
        db.add(Categoria(pluggy_id=cid, description=cid))
    _bank, credit = _contas(db, usuario.id)
    db.add(Cartao(conta_id=credit.id))
    db.commit()

    f_jun = _fatura(db, usuario.id, credit, "fj", 30_000, _em(2026, 6, 15))
    f_jul = _fatura(db, usuario.id, credit, "fl", 50_000, _em(2026, 7, 15))
    repo = TransacaoRepository(db, usuario.id)
    _tx(repo, credit, "c1", -20_000, cat="07010000", quando=_em(2026, 7, 2))
    _tx(repo, credit, "c2", -5_000, cat="05100000", quando=_em(2026, 7, 3))
    _tx(repo, credit, "c3", -8_000, cat="07010000", quando=_em(2026, 6, 2))
    # Vincula as compras às faturas (bill_id).
    for pid, fatura in [("c1", f_jul), ("c2", f_jul), ("c3", f_jun)]:
        tx = repo.get_by_pluggy_id(pid)
        tx.bill_id = fatura.id
    db.commit()

    r = resumo_faturas(db, usuario.id, credit.id)
    assert [b.fatura_id for b in r.buckets] == [f_jun.id, f_jul.id]  # cronológico
    assert [b.total_centavos for b in r.buckets] == [30_000, 50_000]  # total da própria fatura
    jul = r.buckets[1]
    cats = {g.categoria_id: g.total_centavos for g in jul.por_categoria}
    assert cats["07010000"] == 20_000
    assert cats["05100000"] == 5_000
    # Ajuste = total − compras (50_000 − 25_000); fecha a quebra no total da fatura.
    assert cats["__ajuste__"] == 25_000
    # Invariante central: os segmentos somam o total da fatura na vírgula, em toda fatura.
    for b in r.buckets:
        assert sum(g.total_centavos for g in b.por_categoria) == b.total_centavos


def test_resumo_faturas_gasto_e_positivo_com_amount_de_cartao(db, usuario):
    """Cartão traz a compra (DEBIT) com `amount` POSITIVO — sinal oposto ao da conta bancária.
    O gasto por categoria tem de sair positivo mesmo assim (senão a barra inverte e o top-N por
    categoria escolhe as menores)."""
    db.add(Categoria(pluggy_id="07010000", description="c"))
    _b, credit = _contas(db, usuario.id)
    db.add(Cartao(conta_id=credit.id))
    db.commit()
    fatura = _fatura(db, usuario.id, credit, "fp", 30_000, _em(2026, 7, 15))
    repo = TransacaoRepository(db, usuario.id)
    # amount positivo + type DEBIT: a convenção real do cartão (não expressável pelo helper _tx).
    tx = repo.create(
        conta_id=credit.id,
        pluggy_transaction_id="compra",
        date=_em(2026, 7, 2),
        amount_centavos=25_000,  # positivo!
        currency_code="BRL",
        type="DEBIT",
        status="POSTED",
        categoria_pluggy_id="07010000",
        bill_id=fatura.id,
    )
    assert tx.amount_centavos == 25_000

    r = resumo_faturas(db, usuario.id, credit.id)
    assert r.buckets[0].por_categoria[0].total_centavos == 25_000  # positivo, não -25_000
    assert sum(g.total_centavos for g in r.buckets[0].por_categoria) == 30_000  # fecha no total


def test_resumo_faturas_isola_usuario(db, usuario):
    outro = _usuario(db, "outro-fat@mango.test")
    _b, credit = _contas(db, usuario.id)
    db.add(Cartao(conta_id=credit.id))
    db.commit()
    _fatura(db, usuario.id, credit, "meu", 10_000, _em(2026, 7, 15))

    assert resumo_faturas(db, outro.id, credit.id).buckets == []  # cartão de A invisível p/ B


def test_series_isola_usuario(db, usuario):
    outro = _usuario(db, "outro-serie@mango.test")
    bank_a, _ = _contas(db, usuario.id)
    bank_b, _ = _contas(db, outro.id)
    _tx(TransacaoRepository(db, usuario.id), bank_a, "a", 100_000, quando=_em(2026, 6, 10))
    _tx(TransacaoRepository(db, outro.id), bank_b, "b", 999_000, quando=_em(2026, 6, 10))

    serie = montar_series(db, usuario.id, date(2026, 6, 1), date(2026, 6, 30), "semanal")
    assert sum(b.entradas_centavos for b in serie.buckets) == 100_000  # sem os 999_000 de B
