"""Filtros da listagem de transações (§4.5) + vínculo com provento de investimento (§4.9)."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.categoria import Categoria
from app.models.investimento import Investimento, InvestimentoTransacao
from app.models.usuario import Usuario
from app.repositories.assinatura import AssinaturaRepository
from app.repositories.transacao import TransacaoRepository
from tests.helpers import criar_conta


def _criar_tx(repo: TransacaoRepository, conta_id: int, pid: str, **over):
    campos = {
        "date": datetime(2026, 3, 10, tzinfo=UTC),
        "amount_centavos": -2990,
        "currency_code": "BRL",
        "type": "DEBIT",
        "status": "POSTED",
        "merchant_nome": "Loja",
        **over,
    }
    return repo.create(conta_id=conta_id, pluggy_transaction_id=pid, **campos)


def test_filtro_por_assinatura(db: Session, usuario_a: Usuario, client_factory) -> None:
    conta = criar_conta(db, usuario_a.id, "acc-filtro")
    assinatura = AssinaturaRepository(db, usuario_a.id).create(
        nome="Netflix", valor_centavos=2990, periodicidade="mensal"
    )
    repo = TransacaoRepository(db, usuario_a.id)
    com = _criar_tx(repo, conta.id, "t-com", assinatura_id=assinatura.id)
    sem = _criar_tx(repo, conta.id, "t-sem")

    client = client_factory(usuario_a)

    def ids(query: str) -> set[int]:
        resp = client.get(f"/api/transacoes?{query}")
        assert resp.status_code == 200, resp.text
        return {t["id"] for t in resp.json()["items"]}

    assert ids("tem_assinatura=true") == {com.id}
    assert ids("tem_assinatura=false") == {sem.id}
    assert ids(f"assinatura_id={assinatura.id}") == {com.id}
    # assinatura_id específica tem precedência sobre tem_assinatura.
    assert ids(f"assinatura_id={assinatura.id}&tem_assinatura=false") == {com.id}


def _criar_provento(db: Session, item_id: int, usuario_id: int, **over) -> InvestimentoTransacao:
    inv = Investimento(
        usuario_id=usuario_id,
        item_id=item_id,
        pluggy_investment_id=f"inv-{usuario_id}-{over.get('pluggy_id', 'x')}",
        type="EQUITY",
        subtype="REAL_ESTATE_FUND",
        saldo_centavos=0,
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)
    mov = InvestimentoTransacao(
        investimento_id=inv.id,
        pluggy_id=over.get("pluggy_id", "itx-int"),
        type="INTEREST",
        movement_type="CREDIT",
        amount_centavos=over.get("amount_centavos", 1234),
        date=over.get("date", datetime(2026, 7, 11, tzinfo=UTC)),
    )
    db.add(mov)
    db.commit()
    db.refresh(mov)
    return mov


def test_vincular_provento_sugestao_e_isolamento(
    db: Session, usuario_a: Usuario, usuario_b: Usuario, client_factory
) -> None:
    conta = criar_conta(db, usuario_a.id, "acc-prov")
    repo = TransacaoRepository(db, usuario_a.id)
    tx = _criar_tx(
        repo,
        conta.id,
        "t-div",
        type="CREDIT",
        amount_centavos=1234,
        date=datetime(2026, 7, 10, tzinfo=UTC),
        merchant_nome="Rendimento FII",
    )
    mov = _criar_provento(db, conta.item_id, usuario_a.id)

    client = client_factory(usuario_a)
    # sugestão casa por valor + data (±5 dias)
    sug = client.get(f"/api/transacoes/{tx.id}/proventos-sugeridos").json()
    assert [m["id"] for m in sug] == [mov.id]

    # vincula
    resp = client.patch(f"/api/transacoes/{tx.id}", json={"investimento_transacao_id": mov.id})
    assert resp.status_code == 200, resp.text
    assert resp.json()["investimento_transacao_id"] == mov.id

    # já vinculado → não é mais sugerido p/ outra transação de mesmo valor/data
    tx2 = _criar_tx(
        repo,
        conta.id,
        "t-div2",
        type="CREDIT",
        amount_centavos=1234,
        date=datetime(2026, 7, 10, tzinfo=UTC),
    )
    assert client.get(f"/api/transacoes/{tx2.id}/proventos-sugeridos").json() == []

    # isolamento (S3): B não pode vincular sua transação ao provento de A → 400
    conta_b = criar_conta(db, usuario_b.id, "acc-b")
    tx_b = _criar_tx(
        TransacaoRepository(db, usuario_b.id),
        conta_b.id,
        "t-b",
        type="CREDIT",
        amount_centavos=1234,
    )
    neg = client_factory(usuario_b).patch(
        f"/api/transacoes/{tx_b.id}", json={"investimento_transacao_id": mov.id}
    )
    assert neg.status_code == 400


def test_resync_preserva_vinculo_provento(db: Session, usuario_a: Usuario) -> None:
    conta = criar_conta(db, usuario_a.id, "acc-up")
    repo = TransacaoRepository(db, usuario_a.id)
    mov = _criar_provento(db, conta.item_id, usuario_a.id, pluggy_id="itx-up")
    tx = _criar_tx(repo, conta.id, "t-up", type="CREDIT", amount_centavos=1234)
    repo.update(tx, investimento_transacao_id=mov.id)

    # re-sync manda campos do Pluggy; NÃO pode zerar o vínculo do usuário (CAMPOS_USUARIO).
    repo.upsert_by_pluggy_id(
        "t-up",
        conta_id=conta.id,
        date=tx.date,
        amount_centavos=1234,
        currency_code="BRL",
        type="CREDIT",
        status="POSTED",
        investimento_transacao_id=None,
    )
    db.refresh(tx)
    assert tx.investimento_transacao_id == mov.id


def test_descricao_usuario_e_observacoes(db: Session, usuario_a: Usuario, client_factory) -> None:
    conta = criar_conta(db, usuario_a.id, "acc-texto")
    tx = _criar_tx(
        TransacaoRepository(db, usuario_a.id), conta.id, "t-texto", description="PAG*REST XYZ"
    )
    client = client_factory(usuario_a)

    resp = client.patch(
        f"/api/transacoes/{tx.id}",
        json={"descricao_usuario": "Almoço com o time", "observacoes": "Reembolsar o João"},
    )
    assert resp.status_code == 200, resp.text
    lido = client.get(f"/api/transacoes/{tx.id}").json()
    assert lido["descricao_usuario"] == "Almoço com o time"
    assert lido["observacoes"] == "Reembolsar o João"
    assert lido["description"] == "PAG*REST XYZ"  # a do banco fica intacta

    # Campo apagado na UI chega como "" (ou só espaços) → vira NULL, não string vazia.
    client.patch(f"/api/transacoes/{tx.id}", json={"descricao_usuario": "   "})
    assert client.get(f"/api/transacoes/{tx.id}").json()["descricao_usuario"] is None


def test_busca_cobre_textos_do_usuario(db: Session, usuario_a: Usuario, client_factory) -> None:
    conta = criar_conta(db, usuario_a.id, "acc-busca")
    repo = TransacaoRepository(db, usuario_a.id)
    com_descricao = _criar_tx(repo, conta.id, "t-desc", descricao_usuario="Almoço com o time")
    com_observacao = _criar_tx(repo, conta.id, "t-obs", observacoes="Reembolsar o João")
    _criar_tx(repo, conta.id, "t-outra", description="PAG*OUTRA COISA")

    client = client_factory(usuario_a)

    def ids(busca: str) -> set[int]:
        resp = client.get(f"/api/transacoes?busca={busca}")
        assert resp.status_code == 200, resp.text
        return {t["id"] for t in resp.json()["items"]}

    assert ids("almoço") == {com_descricao.id}
    assert ids("joão") == {com_observacao.id}


def test_categoria_de_cobranca_de_assinatura_nao_e_editavel(
    db: Session, usuario_a: Usuario, client_factory
) -> None:
    """§4.5: a categoria vem da assinatura. Duas cobranças da mesma assinatura em categorias
    diferentes é incoerência — o bloqueio é no backend, não só na UI."""
    db.add(Categoria(pluggy_id="02000000", description="Food"))
    db.commit()
    conta = criar_conta(db, usuario_a.id, "acc-assin")
    repo = TransacaoRepository(db, usuario_a.id)
    assinatura = AssinaturaRepository(db, usuario_a.id).create(
        nome="Streaming",
        valor_centavos=2990,
        periodicidade="mensal",
        categoria_id="02000000",
        nomes_transacao=[],
    )
    tx = _criar_tx(repo, conta.id, "t-assin", assinatura_id=assinatura.id)

    client = client_factory(usuario_a)
    resp = client.patch(f"/api/transacoes/{tx.id}", json={"categoria_override_id": "02000000"})
    assert resp.status_code == 400
    assert "assinatura" in resp.json()["detail"]

    # Também bloqueia quando o vínculo é criado no MESMO patch.
    solta = _criar_tx(repo, conta.id, "t-solta")
    assert (
        client.patch(
            f"/api/transacoes/{solta.id}",
            json={"assinatura_id": assinatura.id, "categoria_override_id": "02000000"},
        ).status_code
        == 400
    )

    # E o PATCH recusado não pode deixar rastro: o alias é escrita, e aprender antes das demais
    # validações mudaria o pareamento automático dos próximos syncs por conta de um 400.
    db.refresh(assinatura)
    assert assinatura.nomes_transacao == []

    # Sem tocar na categoria, vincular continua funcionando — e AÍ o alias é aprendido.
    assert (
        client.patch(
            f"/api/transacoes/{solta.id}", json={"assinatura_id": assinatura.id}
        ).status_code
        == 200
    )
    db.refresh(assinatura)
    assert assinatura.nomes_transacao != []


def test_leitura_traz_categoria_efetiva_e_origem(
    db: Session, usuario_a: Usuario, client_factory
) -> None:
    db.add(Categoria(pluggy_id="02000000", description="Food"))
    db.add(Categoria(pluggy_id="03000000", description="Transport"))
    db.commit()
    conta = criar_conta(db, usuario_a.id, "acc-efetiva")
    repo = TransacaoRepository(db, usuario_a.id)
    tx = _criar_tx(repo, conta.id, "t-efetiva", categoria_pluggy_id="02000000")

    client = client_factory(usuario_a)
    lido = client.get(f"/api/transacoes/{tx.id}").json()
    assert lido["categoria_efetiva_id"] == "02000000"
    assert lido["categoria_origem"] == "banco"

    client.patch(f"/api/transacoes/{tx.id}", json={"categoria_override_id": "03000000"})
    lido = client.get(f"/api/transacoes/{tx.id}").json()
    assert lido["categoria_efetiva_id"] == "03000000"
    assert lido["categoria_origem"] == "manual"

    # Desativar a categoria do banco derruba a sugestão para "desconhecida"...
    outra = _criar_tx(repo, conta.id, "t-desativada", categoria_pluggy_id="02000000")
    client.patch("/api/categorias/02000000", json={"ativa": False})
    lido = client.get(f"/api/transacoes/{outra.id}").json()
    assert lido["categoria_efetiva_id"] is None
    assert lido["categoria_origem"] == "desconhecida"
    # ...mas não mexe no ajuste manual, que é escolha explícita.
    assert client.get(f"/api/transacoes/{tx.id}").json()["categoria_efetiva_id"] == "03000000"
