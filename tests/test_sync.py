"""Sync do Pluggy (Fase 1) com cliente HTTP mockado — nada de rede no CI.

Cobre: upsert idempotente, conversão reais→centavos, link billId→fatura, preservação
dos campos do usuário no re-sync, categoryId desconhecido → NULL, e paymentData.
Roda em SQLite e Postgres (fixture `db`).
"""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exceptions import ConflictError, RateLimitError
from app.models.cartao_fatura import (
    Cartao,
    ContaBancaria,
    ContaSaldoReservado,
    Fatura,
    FaturaEncargo,
)
from app.models.categoria import Categoria
from app.models.conta import Conta
from app.models.pluggy import CredencialPluggy, ItemPluggy
from app.models.transacao import Transacao, TransacaoPagamento
from app.models.usuario import Usuario
from app.repositories.assinatura import AssinaturaRepository
from app.repositories.transacao import TransacaoRepository
from app.services import sync as sync_mod
from app.services.sync import sincronizar_usuario

BANK_ID = "acc-bank"
CREDIT_ID = "acc-credit"

ACCOUNTS = [
    {
        "id": BANK_ID,
        "type": "BANK",
        "subtype": "CHECKING_ACCOUNT",
        "name": "Conta Corrente",
        "marketingName": "GOLD Conta Corrente",
        "number": "0001/12345-0",
        "owner": "John Doe",
        "taxNumber": "416.799.495-00",
        "balance": 14317.3,
        "currencyCode": "BRL",
        "createdAt": "2026-06-26T18:59:28.313Z",
        "updatedAt": "2026-06-26T18:59:28.366Z",
        "bankData": {
            "transferNumber": "123/0001/12345-0",
            "closingBalance": 14317.3,
            "automaticallyInvestedBalance": 1431.73,
            "hasReservedBalance": True,
            "reservedBalances": [
                {
                    "name": "Caixinha Para Férias",
                    "identification": "d78fc4e5",
                    "availableAmounts": [
                        {"amount": 1000.04, "remuneration": {"indexer": "CDI", "preFixedRate": 0.3}}
                    ],
                }
            ],
        },
        "creditData": None,
    },
    {
        "id": CREDIT_ID,
        "type": "CREDIT",
        "subtype": "CREDIT_CARD",
        "name": "Mastercard Black",
        "number": "9437",
        "balance": -335.4,
        "currencyCode": "BRL",
        "createdAt": "2026-06-26T18:59:28.376Z",
        "updatedAt": "2026-06-26T18:59:28.422Z",
        "bankData": None,
        "creditData": {
            "level": "BLACK",
            "brand": "MASTERCARD",
            "balanceCloseDate": "2026-06-26",
            "balanceDueDate": "2026-07-01",
            "creditLimit": 300000,
            "availableCreditLimit": 300000,
            "minimumPayment": 67.08,
            "isLimitFlexible": False,
            "holderType": "MAIN",
            "status": "ACTIVE",
        },
    },
]

BILLS = [
    {
        "id": "bill-1",
        "dueDate": "2026-07-01T03:00:00.000Z",
        "totalAmount": 5000,
        "totalAmountCurrencyCode": "BRL",
        "minimumPaymentAmount": 1000,
        "allowsInstallments": True,
        "financeCharges": [{"id": "fc1", "type": "IOF", "amount": 70.5, "currencyCode": "BRL"}],
        "payments": [],
    }
]

TX_BANK = [
    {
        "id": "tx-salario",
        "description": "SALARIO EMPRESA XYZ LTDA",
        "amount": 8500,
        "currencyCode": "BRL",
        "date": "2026-06-05T03:00:00.000Z",
        "categoryId": "01010000",
        "type": "CREDIT",
        "status": "POSTED",
        "createdAt": "2026-06-26T18:59:28.344Z",
    },
    {
        "id": "tx-vivo",
        "description": "VIVO SERVICOS",
        "amount": -120,
        "currencyCode": "BRL",
        "date": "2026-06-20T03:00:00.000Z",
        "categoryId": "07010000",  # NÃO semeada → deve virar NULL
        "type": "DEBIT",
        "status": "POSTED",
        "merchant": {"cnpj": "02449992005638", "businessName": "VIVO S.A.", "category": "Mobile"},
    },
    {
        "id": "tx-boleto",
        "description": "Pagamento de boleto",
        "amount": -100,
        "currencyCode": "BRL",
        "date": "2026-06-26T18:59:20.118Z",
        "categoryId": "05010000",
        "type": "DEBIT",
        "status": "POSTED",
        "paymentData": {
            "paymentMethod": "BOLETO",
            "referenceNumber": "173631925",
            "payer": {
                "name": "Francisco Souza",
                "accountNumber": "11111-7",
                "documentNumber": {"type": "CPF", "value": "111.111.111-11"},
            },
            "receiver": {"name": "Pluggy Brasil", "documentNumber": {"type": "CNPJ", "value": "x"}},
            "boletoMetadata": {"baseAmount": 90, "interestAmount": 10},
        },
    },
]

TX_CREDIT = [
    {
        "id": "tx-cartao",
        "description": "Compra parcelada",
        "amount": -167.7,
        "currencyCode": "BRL",
        "date": "2026-06-15T03:00:00.000Z",
        "categoryId": None,
        "type": "DEBIT",
        "status": "POSTED",
        "creditCardMetadata": {
            "billId": "bill-1",
            "installmentNumber": 1,
            "totalInstallments": 3,
            "totalAmount": -503.1,
        },
    }
]


FII_ID = "inv-fii"
CDB_ID = "inv-cdb"

INVESTMENTS = [
    {
        "id": FII_ID,
        "name": "GGRC11",
        "code": "GGRC11",
        "type": "EQUITY",
        "subtype": "REAL_ESTATE_FUND",
        "balance": 118.4,
        "amount": 118.4,
        "amountOriginal": 119,
        "quantity": 1,
        "value": 118.4,
        "status": "ACTIVE",
        "institution": {"name": "Corretora X", "number": "308"},
        "createdAt": "2026-06-26T18:59:28.313Z",
        "updatedAt": "2026-07-01T18:59:28.313Z",
    },
    {
        "id": CDB_ID,
        "name": "CDB Banco Y",
        "type": "FIXED_INCOME",
        "subtype": "CDB",
        "balance": 1050.25,
        "amount": 1050.25,
        "amountOriginal": 1000,
        "amountProfit": 50.25,
        "taxes": 10.5,
        "taxes2": 0.55,
        "rate": 110,
        "rateType": "CDI",
        "dueDate": "2027-06-26T00:00:00.000Z",
    },
]

INVESTMENT_TXS = {
    FII_ID: [
        {
            "id": "itx-compra",
            "type": "BUY",
            "movementType": "CREDIT",  # sandbox: aplicação vem como CREDIT
            "amount": 119,
            "quantity": 1,
            "value": 119,
            "tradeDate": "2026-06-10T03:00:00.000Z",
            "date": "2026-06-10T03:00:00.000Z",
            "description": "Compra GGRC11",
        },
        {
            # provento real (fora do BUY/SELL do sandbox) — prova o CHECK relaxado (Fase 3)
            "id": "itx-dividendo",
            "type": "DIVIDEND",
            "movementType": "CREDIT",
            "amount": 12.34,
            "date": "2026-07-10T03:00:00.000Z",
            "description": "Rendimento GGRC11",
        },
    ],
}


class FakePluggy:
    """Substitui o PluggyClient: devolve dados canônicos, sem rede."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def item(self, item_id):
        return {"connector": {"id": 611, "name": "Pluggy Bank"}, "status": "UPDATED"}

    def contas(self, item_id):
        return ACCOUNTS

    def faturas(self, account_id):
        return BILLS if account_id == CREDIT_ID else []

    def transacoes(self, account_id, *, desde=None):
        return TX_BANK if account_id == BANK_ID else TX_CREDIT

    def investimentos(self, item_id):
        return INVESTMENTS

    def investimento_transacoes(self, investment_id):
        return INVESTMENT_TXS.get(investment_id, [])


@pytest.fixture
def usuario(db: Session) -> Usuario:
    u = Usuario(nome="Sync", email="sync@mango.test")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture
def conexao(db: Session, usuario: Usuario) -> ItemPluggy:
    # Categorias que o sync deve reconhecer (as demais viram NULL).
    for cid, desc in [("01010000", "Salary"), ("05010000", "Bank Slip")]:
        db.add(Categoria(pluggy_id=cid, description=desc))
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
    # Garante lock limpo entre testes.
    sync_mod._em_andamento.clear()


def test_sync_importa_contas_e_converte_centavos(db, usuario, conexao):
    resumo = sincronizar_usuario(db, usuario.id)

    assert resumo.contas == 2
    assert resumo.transacoes == 4
    assert resumo.transacoes_novas == 4
    assert resumo.investimentos == 2

    contas = {c.pluggy_account_id: c for c in db.scalars(select(Conta)).all()}
    assert contas[BANK_ID].saldo_centavos == 1_431_730  # 14317.30
    assert contas[CREDIT_ID].saldo_centavos == -33_540  # -335.40

    banc = db.get(ContaBancaria, contas[BANK_ID].id)
    assert banc.closing_balance_centavos == 1_431_730
    assert banc.has_reserved_balance is True
    reservados = db.scalars(select(ContaSaldoReservado)).all()
    assert len(reservados) == 1 and reservados[0].valor_centavos == 100_004

    cartao = db.get(Cartao, contas[CREDIT_ID].id)
    assert cartao.brand == "MASTERCARD"
    assert cartao.credit_limit_centavos == 30_000_000


def test_sync_fatura_e_link_billid(db, usuario, conexao):
    sincronizar_usuario(db, usuario.id)

    fatura = db.scalars(select(Fatura)).one()
    assert fatura.pluggy_bill_id == "bill-1"
    assert fatura.total_amount_centavos == 500_000
    encargo = db.scalars(select(FaturaEncargo)).one()
    assert encargo.tipo == "IOF" and encargo.valor_centavos == 7_050

    cartao_tx = db.scalars(
        select(Transacao).where(Transacao.pluggy_transaction_id == "tx-cartao")
    ).one()
    assert cartao_tx.amount_centavos == -16_770
    assert cartao_tx.bill_id == fatura.id  # competência (§4.2)
    assert cartao_tx.installment_number == 1


def test_sync_categoria_desconhecida_vira_null(db, usuario, conexao):
    sincronizar_usuario(db, usuario.id)

    salario = db.scalars(
        select(Transacao).where(Transacao.pluggy_transaction_id == "tx-salario")
    ).one()
    assert salario.amount_centavos == 850_000
    assert salario.categoria_pluggy_id == "01010000"  # semeada → mapeia

    vivo = db.scalars(select(Transacao).where(Transacao.pluggy_transaction_id == "tx-vivo")).one()
    assert vivo.categoria_pluggy_id is None  # não semeada → NULL (não quebra a FK)
    assert vivo.merchant_nome == "VIVO S.A."


def test_sync_payment_data(db, usuario, conexao):
    sincronizar_usuario(db, usuario.id)

    boleto = db.scalars(
        select(Transacao).where(Transacao.pluggy_transaction_id == "tx-boleto")
    ).one()
    pag = db.get(TransacaoPagamento, boleto.id)
    assert pag.metodo == "BOLETO"
    assert pag.payer_doc_valor == "111.111.111-11"
    assert pag.boleto_base_amount_centavos == 9_000


def test_resync_preserva_campos_do_usuario(db, usuario, conexao):
    sincronizar_usuario(db, usuario.id)
    repo = TransacaoRepository(db, usuario.id)
    salario = repo.get_by_pluggy_id("tx-salario")
    repo.update(salario, revisada=True, categoria_override_id="05010000", eh_transferencia=True)

    # Re-sync (forcar ignora o throttle): NÃO pode sobrescrever os campos do usuário.
    sincronizar_usuario(db, usuario.id, forcar=True)
    db.refresh(salario)
    assert salario.revisada is True
    assert salario.categoria_override_id == "05010000"
    assert salario.eh_transferencia is True
    assert salario.categoria_pluggy_id == "01010000"  # sugestão do Pluggy segue atualizando


def test_sync_vincula_assinatura_por_alias(db, usuario, conexao):
    # Assinatura com alias = nome da transação (merchant "VIVO S.A." da tx-vivo).
    assinatura = AssinaturaRepository(db, usuario.id).create(
        nome="Vivo", valor_centavos=12_000, periodicidade="mensal", nomes_transacao=["VIVO S.A."]
    )
    sincronizar_usuario(db, usuario.id)

    repo = TransacaoRepository(db, usuario.id)
    assert repo.get_by_pluggy_id("tx-vivo").assinatura_id == assinatura.id
    assert repo.get_by_pluggy_id("tx-boleto").assinatura_id is None  # sem alias → não vincula


def test_resync_preserva_vinculo_assinatura_manual(db, usuario, conexao):
    sincronizar_usuario(db, usuario.id)
    repo = TransacaoRepository(db, usuario.id)
    # Assinatura SEM alias → o auto-match nunca a vincularia; só o vínculo manual liga.
    assinatura = AssinaturaRepository(db, usuario.id).create(
        nome="Boleto", valor_centavos=10_000, periodicidade="mensal"
    )
    boleto = repo.get_by_pluggy_id("tx-boleto")
    repo.update(boleto, assinatura_id=assinatura.id)

    # re-sync não pode zerar o vínculo (assinatura_id ∈ CAMPOS_USUARIO).
    sincronizar_usuario(db, usuario.id, forcar=True)
    db.refresh(boleto)
    assert boleto.assinatura_id == assinatura.id


def test_throttle_bloqueia_sync_repetido(db, usuario, conexao):
    sincronizar_usuario(db, usuario.id, item_id=conexao.id)
    # ultimo_sync_em recém-setado → dentro da janela de throttle.
    with pytest.raises(RateLimitError):
        sincronizar_usuario(db, usuario.id, item_id=conexao.id)


def test_lock_bloqueia_sync_concorrente(db, usuario, conexao):
    sync_mod._em_andamento.add(conexao.id)
    try:
        with pytest.raises(ConflictError):
            sincronizar_usuario(db, usuario.id, item_id=conexao.id)
    finally:
        sync_mod._em_andamento.discard(conexao.id)


def test_pluggy_error_loga_detalhe_redigido_sem_vazar_ao_cliente(monkeypatch):
    """Router: em PluggyError, detalhe (método/rota/status) vai ao log; ao cliente, msg genérica."""
    import logging

    from app.exceptions import UpstreamError
    from app.pluggy.client import PluggyError
    from app.routers import sync as sync_router

    def _boom(*a, **k):
        raise PluggyError("POST /auth → HTTP 401")

    monkeypatch.setattr(sync_router, "sincronizar_usuario", _boom)

    # Handler direto no logger (nível fixo) — determinístico, sem depender do root/ordering.
    registros: list[logging.LogRecord] = []
    handler = logging.Handler()
    handler.emit = registros.append  # type: ignore[method-assign]
    logger = logging.getLogger("app.sync")
    logger.addHandler(handler)
    nivel_orig = logger.level
    logger.setLevel(logging.WARNING)
    logger.disabled = False  # migrations no boot rodam fileConfig; garante logger ativo no teste
    try:
        with pytest.raises(UpstreamError) as exc:
            sync_router._sincronizar(db=None, usuario_id=1, item_id=None)
    finally:
        logger.removeHandler(handler)
        logger.setLevel(nivel_orig)

    mensagens = [r.getMessage() for r in registros]
    assert exc.value.mensagem == "não foi possível falar com o Pluggy agora"
    assert "HTTP 401" not in exc.value.mensagem  # detalhe não vaza ao cliente
    assert any("POST /auth → HTTP 401" in m for m in mensagens)  # mas fica no log p/ diagnóstico


def test_subtype_fii_normalizado_por_isin():
    """FII de connector real vem como EQUITY/STOCK; o segmento CTF do ISIN B3 o revela."""
    fii = {"type": "EQUITY", "subtype": "STOCK", "isin": "BRXPMLCTF000"}  # XPML11
    assert sync_mod._subtype_investimento(fii) == "REAL_ESTATE_FUND"

    # Ação real (ISIN …ACN…) e BDR não são convertidos.
    acao = {"type": "EQUITY", "subtype": "STOCK", "isin": "BRPETRACNOR9"}  # PETR3
    assert sync_mod._subtype_investimento(acao) == "STOCK"

    # Sandbox já manda certo; direito de subscrição (ISIN …D..M..) fica como veio.
    assert sync_mod._subtype_investimento(
        {"type": "EQUITY", "subtype": "REAL_ESTATE_FUND", "isin": "BRGGRCCTF002"}
    ) == "REAL_ESTATE_FUND"
    assert sync_mod._subtype_investimento(
        {"type": "EQUITY", "subtype": "STOCK", "isin": "BRBTLGD11M11"}  # BTLG12 (direito)
    ) == "STOCK"

    # Sem ISIN e outros tipos: passa direto.
    assert sync_mod._subtype_investimento({"type": "EQUITY", "subtype": "STOCK"}) == "STOCK"
    assert sync_mod._subtype_investimento(
        {"type": "FIXED_INCOME", "subtype": "CDB", "isin": ""}
    ) == "CDB"
