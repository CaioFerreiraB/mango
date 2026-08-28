"""Filtros da listagem de transações (§4.5) + vínculo com provento de investimento (§4.9)."""

from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy.orm import Session

from app.models.categoria import CATEGORIA_PAGAMENTO_FATURA, Categoria
from app.models.investimento import Investimento, InvestimentoTransacao
from app.models.usuario import Usuario
from app.repositories.assinatura import AssinaturaRepository
from app.repositories.transacao import TransacaoRepository
from app.services.periodo import SP, hoje_sp
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


def test_categoria_override_nao_alcanca_categoria_de_outro_usuario(
    db: Session, usuario_a: Usuario, usuario_b: Usuario, client_factory
) -> None:
    """S3: a FK só exige que a linha exista, e `categoria` mistura linha global com linha de
    usuário — sem checagem de posse, B gravava na própria transação o id da categoria PRIVADA de A.
    """
    cat_de_a = (
        client_factory(usuario_a)
        .post("/api/categorias", json={"nome": "Segredo de A"})
        .json()["pluggy_id"]
    )
    conta = criar_conta(db, usuario_b.id, "acc-b")
    tx = _criar_tx(TransacaoRepository(db, usuario_b.id), conta.id, "t-de-b")

    resposta = client_factory(usuario_b).patch(
        f"/api/transacoes/{tx.id}", json={"categoria_override_id": cat_de_a}
    )
    assert resposta.status_code == 400
    db.refresh(tx)
    assert tx.categoria_override_id is None  # e a transação não foi tocada

    # A global do Pluggy continua valendo para os dois — a recusa é de posse, não de categoria.
    db.add(Categoria(pluggy_id="07000000", description="Services"))
    db.commit()
    assert (
        client_factory(usuario_b)
        .patch(f"/api/transacoes/{tx.id}", json={"categoria_override_id": "07000000"})
        .status_code
        == 200
    )


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


# --- fila de revisão + data de corte (§4.3) -------------------------------------------


def test_pendente_revisao_respeita_o_corte(db: Session, usuario_a: Usuario, client_factory) -> None:
    """`pendente_revisao` é o conceito de produto ("está na fila?") e obedece ao corte do usuário;
    `revisada` continua sendo o filtro cru da coluna e ignora o corte."""
    conta = criar_conta(db, usuario_a.id, "acc-revisao")
    repo = TransacaoRepository(db, usuario_a.id)
    antiga = _criar_tx(repo, conta.id, "t-antiga", date=datetime(2026, 2, 20, tzinfo=UTC))
    # 01/03 02:00 UTC = 28/02 23:00 em SP → cai ANTES do corte (a comparação é no fuso SP).
    borda = _criar_tx(repo, conta.id, "t-borda", date=datetime(2026, 3, 1, 2, tzinfo=UTC))
    no_corte = _criar_tx(repo, conta.id, "t-no-corte", date=datetime(2026, 3, 1, 12, tzinfo=UTC))
    nova = _criar_tx(repo, conta.id, "t-nova", date=datetime(2026, 3, 10, tzinfo=UTC))
    ja_revisada = _criar_tx(
        repo, conta.id, "t-revisada", date=datetime(2026, 3, 12, tzinfo=UTC), revisada=True
    )

    client = client_factory(usuario_a)

    def ids(query: str) -> set[int]:
        resp = client.get(f"/api/transacoes?{query}")
        assert resp.status_code == 200, resp.text
        corpo = resp.json()
        assert corpo["total"] == len(corpo["items"])  # a contagem usa os mesmos filtros
        return {t["id"] for t in corpo["items"]}

    nao_revisadas = {antiga.id, borda.id, no_corte.id, nova.id}
    # Sem corte, "pendente" é exatamente "não revisada".
    assert ids("pendente_revisao=true") == nao_revisadas

    usuario_a.revisao_desde = date(2026, 3, 1)
    db.commit()

    # O corte é inclusivo: o próprio dia 01/03 (no fuso SP) já pede revisão.
    assert ids("pendente_revisao=true") == {no_corte.id, nova.id}
    # O complemento traz as revisadas E as ignoradas — ninguém some da listagem.
    assert ids("pendente_revisao=false") == {antiga.id, borda.id, ja_revisada.id}
    # O filtro cru da coluna não mudou de significado com o corte.
    assert ids("revisada=false") == nao_revisadas
    assert ids("revisada=true") == {ja_revisada.id}


# --- padrões de exibição da listagem (§4.2/§4.4) ---------------------------------------


def test_ocultar_pagamento_fatura_usa_a_categoria_efetiva(
    db: Session, usuario_a: Usuario, client_factory
) -> None:
    """§4.4: o filtro segue a precedência de §4.5, não a categoria crua. Recategorizar um pagamento
    à mão o traz de volta à listagem; ser pagamento por regra já basta para escondê-lo."""
    db.add(Categoria(pluggy_id=CATEGORIA_PAGAMENTO_FATURA, description="Pagamento de cartão"))
    db.add(Categoria(pluggy_id="02000000", description="Food"))
    db.commit()
    conta = criar_conta(db, usuario_a.id, "acc-pgto")
    repo = TransacaoRepository(db, usuario_a.id)
    do_banco = _criar_tx(repo, conta.id, "t-banco", categoria_pluggy_id=CATEGORIA_PAGAMENTO_FATURA)
    por_regra = _criar_tx(repo, conta.id, "t-regra", categoria_regra_id=CATEGORIA_PAGAMENTO_FATURA)
    por_mao = _criar_tx(
        repo,
        conta.id,
        "t-mao",
        categoria_pluggy_id="02000000",
        categoria_override_id=CATEGORIA_PAGAMENTO_FATURA,
    )
    recategorizada = _criar_tx(
        repo,
        conta.id,
        "t-recat",
        categoria_pluggy_id=CATEGORIA_PAGAMENTO_FATURA,
        categoria_override_id="02000000",
    )
    sem_categoria = _criar_tx(repo, conta.id, "t-sem-cat")

    client = client_factory(usuario_a)

    def ids(query: str) -> set[int]:
        resp = client.get(f"/api/transacoes?{query}")
        assert resp.status_code == 200, resp.text
        corpo = resp.json()
        assert corpo["total"] == len(corpo["items"])  # a contagem usa os mesmos filtros
        return {t["id"] for t in corpo["items"]}

    todas = {do_banco.id, por_regra.id, por_mao.id, recategorizada.id, sem_categoria.id}
    assert ids("") == todas  # desligado por padrão no backend
    # Some o que É pagamento pela categoria efetiva — inclusive quando isso veio de uma regra.
    # Fica quem o usuário recategorizou à mão e quem não tem categoria nenhuma (NULL não é
    # pagamento de fatura — a armadilha do `!=`).
    assert ids("ocultar_pagamento_fatura=true") == {recategorizada.id, sem_categoria.id}


def test_ocultar_futuras_corta_no_fim_do_dia_de_hoje(
    db: Session, usuario_a: Usuario, client_factory
) -> None:
    """§4.2: o corte é o fim do dia civil em SP. Um lançamento de hoje às 23h já está no dia
    seguinte em UTC e continua visível — é a borda que a comparação ingênua em UTC erraria."""
    hoje = hoje_sp()
    conta = criar_conta(db, usuario_a.id, "acc-futuras")
    repo = TransacaoRepository(db, usuario_a.id)

    def em_sp(dia: date, hora: int) -> datetime:
        return datetime.combine(dia, time(hora), tzinfo=SP).astimezone(UTC)

    ontem = _criar_tx(repo, conta.id, "t-ontem", date=em_sp(hoje - timedelta(days=1), 12))
    borda = _criar_tx(repo, conta.id, "t-borda", date=em_sp(hoje, 23))
    parcela = _criar_tx(
        repo,
        conta.id,
        "t-parcela",
        date=em_sp(hoje + timedelta(days=40), 12),
        installment_number=2,
        total_installments=6,
    )

    client = client_factory(usuario_a)

    def ids(query: str) -> set[int]:
        resp = client.get(f"/api/transacoes?{query}")
        assert resp.status_code == 200, resp.text
        corpo = resp.json()
        assert corpo["total"] == len(corpo["items"])
        return {t["id"] for t in corpo["items"]}

    assert ids("") == {ontem.id, borda.id, parcela.id}  # desligado por padrão no backend
    assert ids("ocultar_futuras=true") == {ontem.id, borda.id}
    # Convive com `fim`: prevalece sempre o limite mais apertado, venha de qual dos dois vier.
    fim_amplo = (hoje + timedelta(days=60)).isoformat()
    assert ids(f"ocultar_futuras=true&fim={fim_amplo}") == {ontem.id, borda.id}
    fim_estreito = (hoje - timedelta(days=1)).isoformat()
    assert ids(f"ocultar_futuras=true&fim={fim_estreito}") == {ontem.id}
