"""Serviço de sincronização com o Pluggy (§4.3). Puxa contas/faturas/transações e faz
upsert idempotente, preservando os campos do usuário (§4.4/§4.5).

Segurança:
- Escopo de usuário em toda leitura/escrita via repositórios (`UserScopedRepository`, S3).
  Tabelas-detalhe 1:1 (`conta_bancaria`, `cartao`, encargos, pagamento) são alcançadas pela
  conta/fatura-pai já escopada — o `db.get(...)` por PK usa ids que nós mesmos geramos, nunca
  input do cliente.
- Throttle + lock por item contra abuso/corrida (S5).
- `apiKey` só vive na instância do `PluggyClient` (S1).

`ponytail:` roda inline no request (best-effort). Se ficar lento, mover para um worker; o
lock é por processo (suficiente p/ desktop e self-hosted de 1 worker).
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import settings
from app.enums import CONTA_SUBTYPE, CONTA_TYPE, TRANSACAO_STATUS, TRANSACAO_TYPE
from app.exceptions import ConflictError, NotFoundError, RateLimitError
from app.models.cartao_fatura import (
    Cartao,
    ContaBancaria,
    ContaSaldoReservado,
    FaturaEncargo,
)
from app.models.categoria import Categoria
from app.models.conta import Conta
from app.models.investimento import Investimento, InvestimentoTransacao
from app.models.transacao import Transacao, TransacaoPagamento
from app.pluggy.client import PluggyClient
from app.repositories.conta import ContaRepository
from app.repositories.fatura import FaturaRepository
from app.repositories.investimento import InvestimentoRepository
from app.repositories.pluggy import (
    CredencialPluggyRepository,
    InstituicaoRepository,
    ItemPluggyRepository,
)
from app.repositories.transacao import TransacaoRepository
from app.services.assinatura_match import aplicar_match_assinaturas
from app.services.ativo_agrupamento import agrupar_renda_fixa
from app.services.orcamento_mensal import materializar_mes
from app.services.periodo import SP
from app.services.saldo_diario import registrar_snapshot, registrar_snapshot_investimento
from app.services.transferencia import aplicar_regras_transferencia

logger = logging.getLogger("app.sync")

# Lock por item (por processo). Impede sync concorrente do mesmo item (corrida nos upserts).
_lock = threading.Lock()
_em_andamento: set[int] = set()


@dataclass
class ResumoSync:
    itens: int = 0
    contas: int = 0
    transacoes: int = 0
    transacoes_novas: int = 0
    investimentos: int = 0


# --- conversões (dado externo → nosso schema) ----------------------------------------


def reais_para_centavos(valor: object) -> int | None:
    """Reais decimais do Pluggy → INTEGER centavos (decisão #2). Decimal evita erro de float."""
    if valor is None:
        return None
    return int((Decimal(str(valor)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _parse_dt(valor: str | None) -> datetime | None:
    if not valor:
        return None
    return datetime.fromisoformat(valor.replace("Z", "+00:00"))


def _coerce(valor: object, permitidos: tuple[str, ...]) -> str | None:
    """Só aceita valores previstos nas CHECK; o resto vira NULL (não derruba o sync)."""
    return valor if valor in permitidos else None  # type: ignore[return-value]


def _num(valor: object) -> Decimal | None:
    """Números de precisão (cotação/quantidade/taxas %) → Decimal, sem passar por float."""
    if valor is None:
        return None
    return Decimal(str(valor))


def _agora() -> datetime:
    return datetime.now(UTC)


# --- controle de concorrência / throttle ---------------------------------------------


def _throttled(item) -> bool:
    if item.ultimo_sync_em is None:
        return False
    ultimo = item.ultimo_sync_em
    if ultimo.tzinfo is None:  # SQLite devolve naive → assume UTC
        ultimo = ultimo.replace(tzinfo=UTC)
    return _agora() - ultimo < timedelta(minutes=settings.sync_min_intervalo_min)


def _adquirir(item_id: int) -> None:
    with _lock:
        if item_id in _em_andamento:
            raise ConflictError("sincronização desta conexão já está em andamento")
        _em_andamento.add(item_id)


def _liberar(item_id: int) -> None:
    with _lock:
        _em_andamento.discard(item_id)


# --- entrada pública -----------------------------------------------------------------


def sincronizar_usuario(
    db: Session, usuario_id: int, *, item_id: int | None = None, forcar: bool = False
) -> ResumoSync:
    """Sincroniza um item (ou todos) do usuário. `item_id` fora do escopo → 404 (S3)."""
    creds = CredencialPluggyRepository(db, usuario_id).list()
    if not creds:
        raise NotFoundError("nenhuma credencial Pluggy configurada")
    cred = creds[0]

    item_repo = ItemPluggyRepository(db, usuario_id)
    if item_id is not None:
        item = item_repo.get(item_id)
        if item is None:
            raise NotFoundError("conexão não encontrada")
        itens = [item]
    else:
        itens = item_repo.list()

    categorias_validas = set(db.scalars(select(Categoria.pluggy_id)).all())
    # 1º sync de qualquer item → pareia sobre todo o histórico; senão, só a janela recente.
    primeiro_sync = any(it.ultimo_sync_em is None for it in itens)
    resumo = ResumoSync()
    # client_id_cifrado/client_secret_cifrado retornam em claro na leitura (EncryptedStr).
    with PluggyClient(cred.client_id_cifrado, cred.client_secret_cifrado) as client:
        for item in itens:
            if _throttled(item):
                if item_id is not None and not forcar:
                    raise RateLimitError(
                        "aguarde um instante antes de atualizar esta conexão novamente"
                    )
                continue  # sync-de-todos: pula conexões recém-atualizadas
            _adquirir(item.id)
            try:
                _sincronizar_item(db, usuario_id, item, client, categorias_validas, resumo)
                resumo.itens += 1
            finally:
                _liberar(item.id)

    # Pareamento roda no fim, sobre TODAS as contas do usuário (as duas pernas podem estar
    # em itens/bancos distintos). Idempotente (§4.4).
    if resumo.itens:
        janela = None if primeiro_sync else date.today() - timedelta(days=settings.sync_janela_dias)
        aplicar_regras_transferencia(db, usuario_id, desde=janela)
        # Auto-vincula transações a assinaturas por nome exato (§4.7). Idempotente, não toca vínculo
        # manual (assinatura_id já preenchido). Mesma janela da passada de transferência.
        aplicar_match_assinaturas(db, usuario_id, desde=janela)
        # Agrupa novas posições de renda fixa num ativo (§4.9). Best-effort: um bug aqui não pode
        # derrubar um sync já commitado. Só preenche ativo_id NULL (idempotente, não toca ajuste
        # manual).
        try:
            agrupar_renda_fixa(db, usuario_id)
        except Exception:
            db.rollback()
            logger.exception("pós-processamento do sync falhou (agrupamento de ativos)")
        # Pós-processamento best-effort: um bug aqui não pode derrubar um sync que já commitou as
        # transações. Materialização do mês corrente (§4.6). Assinaturas não são mais detectadas no
        # sync — o usuário busca sob demanda pelo dialog (§4.7).
        try:
            hoje = datetime.now(SP).date()
            materializar_mes(db, usuario_id, hoje.year, hoje.month)
        except Exception:
            db.rollback()
            logger.exception("pós-processamento do sync falhou (orçamentos)")
    return resumo


# --- por item ------------------------------------------------------------------------


def _sincronizar_item(
    db: Session,
    usuario_id: int,
    item,
    client: PluggyClient,
    categorias_validas: set[str],
    resumo: ResumoSync,
) -> None:
    inst_repo = InstituicaoRepository(db, usuario_id)
    conta_repo = ContaRepository(db, usuario_id)
    fatura_repo = FaturaRepository(db, usuario_id)
    tx_repo = TransacaoRepository(db, usuario_id)
    item_repo = ItemPluggyRepository(db, usuario_id)

    pluggy_item_id = item.pluggy_item_id  # decifrado na leitura
    item_data = client.item(pluggy_item_id)
    connector = item_data.get("connector") or {}
    item_repo.update(
        item,
        connector_id=connector.get("id"),
        connector_nome=connector.get("name"),
        status=item_data.get("status"),
    )
    inst = inst_repo.upsert_by_connector(
        connector.get("id"), nome=connector.get("name") or "Instituição"
    )

    # 1º sync: histórico completo (cap de páginas protege). Depois: janela incremental.
    desde = (
        None
        if item.ultimo_sync_em is None
        else date.today() - timedelta(days=settings.sync_janela_dias)
    )

    for acc in client.contas(pluggy_item_id):
        tipo = _coerce(acc.get("type"), CONTA_TYPE)
        if tipo is None:
            continue
        conta = conta_repo.upsert_by_pluggy_id(
            acc["id"],
            item_id=item.id,
            instituicao_id=inst.id,
            type=tipo,
            subtype=_coerce(acc.get("subtype"), CONTA_SUBTYPE),
            nome=acc.get("name"),
            marketing_name=acc.get("marketingName"),
            numero=acc.get("number"),
            owner=acc.get("owner"),
            tax_number=acc.get("taxNumber"),
            saldo_centavos=reais_para_centavos(acc.get("balance")) or 0,
            currency_code=acc.get("currencyCode") or "BRL",
            pluggy_criado_em=_parse_dt(acc.get("createdAt")),
            pluggy_atualizado_em=_parse_dt(acc.get("updatedAt")),
        )
        resumo.contas += 1

        if tipo == "BANK":
            registrar_snapshot(db, conta)  # ponto do dia p/ o sparkline de saldo (idempotente)
        if tipo == "BANK" and acc.get("bankData"):
            _upsert_conta_bancaria(db, conta.id, acc["bankData"])
        elif tipo == "CREDIT" and acc.get("creditData"):
            _upsert_cartao(db, conta.id, acc["creditData"])

        bill_map: dict[str, int] = {}
        if tipo == "CREDIT":
            for bill in client.faturas(acc["id"]):
                due = _parse_dt(bill.get("dueDate"))
                if due is None:
                    continue
                fatura = fatura_repo.upsert_by_pluggy_id(
                    bill["id"],
                    cartao_id=conta.id,  # Fatura.cartao_id → cartao.conta_id == conta.id
                    due_date=due,
                    total_amount_centavos=reais_para_centavos(bill.get("totalAmount")) or 0,
                    total_amount_currency_code=bill.get("totalAmountCurrencyCode"),
                    minimum_payment_centavos=reais_para_centavos(bill.get("minimumPaymentAmount")),
                    allows_installments=bill.get("allowsInstallments"),
                )
                bill_map[bill["id"]] = fatura.id
                _recriar_encargos(db, fatura.id, bill.get("financeCharges") or [])

        _upsert_transacoes(db, conta, tx_repo, client, desde, categorias_validas, bill_map, resumo)
        db.commit()

    _upsert_investimentos(db, usuario_id, item, client, resumo)
    db.commit()

    item_repo.update(item, ultimo_sync_em=_agora(), status=item_data.get("status"))


# --- detalhes de conta ---------------------------------------------------------------


def _upsert_conta_bancaria(db: Session, conta_id: int, bank: dict) -> None:
    campos = {
        "transfer_number": bank.get("transferNumber"),
        "closing_balance_centavos": reais_para_centavos(bank.get("closingBalance")),
        "automatically_invested_balance_centavos": reais_para_centavos(
            bank.get("automaticallyInvestedBalance")
        ),
        "overdraft_contracted_limit_centavos": reais_para_centavos(
            bank.get("overdraftContractedLimit")
        ),
        "overdraft_used_limit_centavos": reais_para_centavos(bank.get("overdraftUsedLimit")),
        "unarranged_overdraft_amount_centavos": reais_para_centavos(
            bank.get("unarrangedOverdraftAmount")
        ),
        "has_reserved_balance": bank.get("hasReservedBalance"),
    }
    obj = db.get(ContaBancaria, conta_id)
    if obj is None:
        db.add(ContaBancaria(conta_id=conta_id, **campos))
    else:
        for k, v in campos.items():
            setattr(obj, k, v)
    db.flush()

    # Caixinhas: derivadas → recria a cada sync.
    db.execute(delete(ContaSaldoReservado).where(ContaSaldoReservado.conta_bancaria_id == conta_id))
    for rb in bank.get("reservedBalances") or []:
        aa = (rb.get("availableAmounts") or [{}])[0]
        rem = aa.get("remuneration") or {}
        db.add(
            ContaSaldoReservado(
                conta_bancaria_id=conta_id,
                nome=rb.get("name"),
                identificacao=rb.get("identification"),
                valor_centavos=reais_para_centavos(aa.get("amount")),
                rem_indexer=rem.get("indexer"),
                rem_rate_type=rem.get("rateType"),
                rem_pre_fixed_rate=rem.get("preFixedRate"),
                rem_periodicity=rem.get("ratePeriodicity"),
            )
        )


def _upsert_cartao(db: Session, conta_id: int, credit: dict) -> None:
    campos = {
        "level": credit.get("level"),
        "brand": credit.get("brand"),
        "brand_additional_info": credit.get("brandAdditionalInfo"),
        "balance_close_date": _parse_date(credit.get("balanceCloseDate")),
        "balance_due_date": _parse_date(credit.get("balanceDueDate")),
        "credit_limit_centavos": reais_para_centavos(credit.get("creditLimit")),
        "available_credit_limit_centavos": reais_para_centavos(credit.get("availableCreditLimit")),
        "balance_foreign_currency_centavos": reais_para_centavos(
            credit.get("balanceForeignCurrency")
        ),
        "minimum_payment_centavos": reais_para_centavos(credit.get("minimumPayment")),
        "is_limit_flexible": credit.get("isLimitFlexible"),
        "holder_type": credit.get("holderType"),
        "status": credit.get("status"),
    }
    obj = db.get(Cartao, conta_id)
    if obj is None:
        db.add(Cartao(conta_id=conta_id, **campos))
    else:
        for k, v in campos.items():
            setattr(obj, k, v)
    db.flush()


def _parse_date(valor: str | None) -> date | None:
    if not valor:
        return None
    return date.fromisoformat(valor[:10])


def _recriar_encargos(db: Session, fatura_id: int, charges: list[dict]) -> None:
    db.execute(delete(FaturaEncargo).where(FaturaEncargo.fatura_id == fatura_id))
    for fc in charges:
        valor = reais_para_centavos(fc.get("amount"))
        tipo = fc.get("type")
        if valor is None or not tipo:
            continue
        db.add(
            FaturaEncargo(
                fatura_id=fatura_id,
                tipo=tipo,
                valor_centavos=valor,
                currency_code=fc.get("currencyCode"),
                additional_info=fc.get("additionalInfo"),
            )
        )


# --- transações ----------------------------------------------------------------------


def _upsert_transacoes(
    db: Session,
    conta: Conta,
    tx_repo: TransacaoRepository,
    client: PluggyClient,
    desde: date | None,
    categorias_validas: set[str],
    bill_map: dict[str, int],
    resumo: ResumoSync,
) -> None:
    existentes = set(
        db.scalars(
            select(Transacao.pluggy_transaction_id).where(Transacao.conta_id == conta.id)
        ).all()
    )
    for tx in client.transacoes(conta.pluggy_account_id, desde=desde):
        tipo = _coerce(tx.get("type"), TRANSACAO_TYPE)
        valor = reais_para_centavos(tx.get("amount"))
        quando = _parse_dt(tx.get("date"))
        if tipo is None or valor is None or quando is None:
            continue  # dado externo incompleto — não derruba o sync (S4)

        ccm = tx.get("creditCardMetadata") or {}
        merchant = tx.get("merchant") or {}
        cat = tx.get("categoryId")
        nova = tx["id"] not in existentes

        tx_repo.upsert_by_pluggy_id(
            tx["id"],
            conta_id=conta.id,
            date=quando,
            description=tx.get("description"),
            description_raw=tx.get("descriptionRaw"),
            amount_centavos=valor,
            amount_in_account_currency_centavos=reais_para_centavos(
                tx.get("amountInAccountCurrency")
            ),
            currency_code=tx.get("currencyCode") or "BRL",
            type=tipo,
            status=_coerce(tx.get("status"), TRANSACAO_STATUS) or "POSTED",
            balance_centavos=reais_para_centavos(tx.get("balance")),
            categoria_pluggy_id=cat if cat in categorias_validas else None,
            merchant_cnpj=merchant.get("cnpj"),
            merchant_cnae=merchant.get("cnae"),
            merchant_nome=merchant.get("businessName"),
            merchant_categoria=merchant.get("category"),
            operation_type=tx.get("operationType"),
            provider_code=tx.get("providerCode"),
            provider_id=tx.get("providerId"),
            ordem=tx.get("order"),
            bill_id=bill_map.get(ccm.get("billId")),
            installment_number=ccm.get("installmentNumber"),
            total_installments=ccm.get("totalInstallments"),
            total_amount_centavos=reais_para_centavos(ccm.get("totalAmount")),
            payee_mcc=ccm.get("payeeMCC"),
            pluggy_criado_em=_parse_dt(tx.get("createdAt")),
            pluggy_atualizado_em=_parse_dt(tx.get("updatedAt")),
        )
        # Reobter para o id (o upsert já fez commit/refresh internamente).
        obj = tx_repo.get_by_pluggy_id(tx["id"])
        if tx.get("paymentData") and obj is not None:
            _upsert_pagamento(db, obj.id, tx["paymentData"])
        resumo.transacoes += 1
        if nova:
            resumo.transacoes_novas += 1


# --- investimentos (§4.9) -------------------------------------------------------------


def _subtype_investimento(data: dict) -> str | None:
    """Normaliza o subtype de FII. Connectors reais (ex.: NuInvest) devolvem FII como
    `EQUITY`/`STOCK` — só o sandbox usa `REAL_ESTATE_FUND`. O segmento de tipo do ISIN B3
    (posições 7-9) desambigua: cota de fundo é `CTF` (FII; ETF nunca colide, vem como
    `type=ETF`), enquanto ação é `ACN` e BDR é `BDR`.

    ponytail: direito/recibo de subscrição de FII (ticker …12/13, ISIN `…D..M..`) fica como
    veio — instrumento temporário que vira a cota …11 no próximo evento; classificá-lo não
    compensa a fragilidade (o `D…` também abre direito de ação)."""
    subtype = data.get("subtype")
    isin = data.get("isin") or ""
    if data.get("type") == "EQUITY" and subtype != "REAL_ESTATE_FUND" and isin[6:9] == "CTF":
        return "REAL_ESTATE_FUND"
    return subtype


def _upsert_investimentos(
    db: Session, usuario_id: int, item, client: PluggyClient, resumo: ResumoSync
) -> None:
    """Upsert dos investimentos do item + snapshot do dia + movimentos. Valores já
    calculados pelo Pluggy (#5); campos variam por tipo → nullable (S4)."""
    inv_repo = InvestimentoRepository(db, usuario_id)
    for data in client.investimentos(item.pluggy_item_id):
        if not data.get("id") or not data.get("type"):
            continue  # dado externo incompleto — não derruba o sync (S4)
        emissora = data.get("institution") or {}
        inv = inv_repo.upsert_by_pluggy_id(
            data["id"],
            item_id=item.id,
            nome=data.get("name"),
            numero=data.get("number"),
            type=data["type"],
            subtype=_subtype_investimento(data),
            saldo_centavos=reais_para_centavos(data.get("balance")) or 0,
            amount_centavos=reais_para_centavos(data.get("amount")),
            amount_original_centavos=reais_para_centavos(data.get("amountOriginal")),
            taxes_centavos=reais_para_centavos(data.get("taxes")),
            taxes2_centavos=reais_para_centavos(data.get("taxes2")),
            amount_profit_centavos=reais_para_centavos(data.get("amountProfit")),
            amount_withdrawal_centavos=reais_para_centavos(data.get("amountWithdrawal")),
            quantity=_num(data.get("quantity")),
            value_unitario=_num(data.get("value")),
            code=data.get("code"),
            isin=data.get("isin"),
            issuer=data.get("issuer"),
            issuer_cnpj=data.get("issuerCNPJ"),
            due_date=_parse_dt(data.get("dueDate")),
            issue_date=_parse_dt(data.get("issueDate")),
            purchase_date=_parse_dt(data.get("purchaseDate")),
            grace_period_date=_parse_dt(data.get("gracePeriodDate")),
            rate=_num(data.get("rate")),
            rate_type=data.get("rateType"),
            rate_periodicity=data.get("ratePeriodicity"),
            fixed_annual_rate=_num(data.get("fixedAnnualRate")),
            annual_rate=_num(data.get("annualRate")),
            last_month_rate=_num(data.get("lastMonthRate")),
            last_twelve_months_rate=_num(data.get("lastTwelveMonthsRate")),
            tax_exempt=data.get("taxExempt"),
            owner=data.get("owner"),
            status=data.get("status"),
            instituicao_emissora_nome=emissora.get("name"),
            instituicao_emissora_numero=emissora.get("number"),
            pluggy_criado_em=_parse_dt(data.get("createdAt")),
            pluggy_atualizado_em=_parse_dt(data.get("updatedAt")),
        )
        registrar_snapshot_investimento(db, inv)
        _upsert_investimento_transacoes(db, inv, client)
        resumo.investimentos += 1


def _upsert_investimento_transacoes(db: Session, inv: Investimento, client: PluggyClient) -> None:
    """Movimentos/proventos do investimento (`GET /investments/{id}/transactions`).
    Tabela-detalhe alcançada pelo pai já escopado (como `TransacaoPagamento`)."""
    # Só os movimentos vindos do Pluggy entram na reconciliação (por `pluggy_id`); aportes manuais
    # (pluggy_id NULL, `manual=True`) ficam de fora e são preservados no re-sync.
    existentes = {
        obj.pluggy_id: obj
        for obj in db.scalars(
            select(InvestimentoTransacao).where(
                InvestimentoTransacao.investimento_id == inv.id,
                InvestimentoTransacao.pluggy_id.is_not(None),
            )
        )
    }
    for t in client.investimento_transacoes(inv.pluggy_investment_id):
        valor = reais_para_centavos(t.get("amount"))
        if not t.get("id") or valor is None:
            continue  # dado externo incompleto (S4)
        campos = {
            "investimento_id": inv.id,
            "type": t.get("type"),
            "movement_type": t.get("movementType"),
            "amount_centavos": valor,
            "value_unitario": _num(t.get("value")),
            "quantity": _num(t.get("quantity")),
            "net_amount_centavos": reais_para_centavos(t.get("netAmount")),
            "expenses_centavos": reais_para_centavos(t.get("expenses")),
            "trade_date": _parse_dt(t.get("tradeDate")),
            "date": _parse_dt(t.get("date")),
            "description": t.get("description"),
            "brokerage_number": t.get("brokerageNumber"),
        }
        obj = existentes.get(t["id"])
        if obj is None:
            db.add(InvestimentoTransacao(pluggy_id=t["id"], **campos))
        else:
            for k, v in campos.items():
                setattr(obj, k, v)
    db.flush()


def _upsert_pagamento(db: Session, transacao_id: int, pay: dict) -> None:
    payer = pay.get("payer") or {}
    receiver = pay.get("receiver") or {}
    boleto = pay.get("boletoMetadata") or {}
    payer_doc = payer.get("documentNumber") or {}
    receiver_doc = receiver.get("documentNumber") or {}
    campos = {
        "metodo": pay.get("paymentMethod"),
        "reason": pay.get("reason"),
        "reference_number": pay.get("referenceNumber"),
        "receiver_reference_id": pay.get("receiverReferenceId"),
        "payer_nome": payer.get("name"),
        "payer_conta": payer.get("accountNumber"),
        "payer_agencia": payer.get("branchNumber"),
        "payer_doc_tipo": payer_doc.get("type"),
        "payer_doc_valor": payer_doc.get("value"),
        "receiver_nome": receiver.get("name"),
        "receiver_conta": receiver.get("accountNumber"),
        "receiver_agencia": receiver.get("branchNumber"),
        "receiver_doc_tipo": receiver_doc.get("type"),
        "receiver_doc_valor": receiver_doc.get("value"),
        "boleto_base_amount_centavos": reais_para_centavos(boleto.get("baseAmount")),
        "boleto_interest_centavos": reais_para_centavos(boleto.get("interestAmount")),
        "boleto_discount_centavos": reais_para_centavos(boleto.get("discountAmount")),
        "boleto_penalty_centavos": reais_para_centavos(boleto.get("penaltyAmount")),
    }
    obj = db.get(TransacaoPagamento, transacao_id)
    if obj is None:
        db.add(TransacaoPagamento(transacao_id=transacao_id, **campos))
    else:
        for k, v in campos.items():
            setattr(obj, k, v)
    db.flush()
