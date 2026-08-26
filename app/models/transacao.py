"""Transações (§4.3–4.5) — `GET /v2/transactions`. Dado do Pluggy + flags do usuário.

Campos graváveis pelo usuário (§4 crud.md): `eh_transferencia`, `revisada`,
`categoria_override_id`, `categoria_ajustada_usuario`, `descricao_usuario`, `observacoes`.
Re-sync NÃO sobrescreve o override nem os flags. `contraparte_id` (auto-FK) liga as duas pernas
de uma transferência (§4.4).
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.enums import TRANSACAO_STATUS, TRANSACAO_TYPE, TRANSFERENCIA_ORIGEM, check_in
from app.models.mixins import TimestampMixin, UserOwnedMixin


class Transacao(UserOwnedMixin, TimestampMixin, Base):
    __tablename__ = "transacao"
    __table_args__ = (
        check_in("type", TRANSACAO_TYPE, "type"),
        check_in("status", TRANSACAO_STATUS, "status"),
        check_in("transferencia_origem", TRANSFERENCIA_ORIGEM, "transferencia_origem"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    conta_id: Mapped[int] = mapped_column(
        ForeignKey("conta.id", ondelete="CASCADE"), nullable=False, index=True
    )
    pluggy_transaction_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    description_raw: Mapped[str | None] = mapped_column(Text)
    amount_centavos: Mapped[int] = mapped_column(BigInteger, nullable=False)  # round(amount*100)
    amount_in_account_currency_centavos: Mapped[int | None] = mapped_column(BigInteger)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    type: Mapped[str] = mapped_column(String(8), nullable=False)  # DEBIT | CREDIT
    status: Mapped[str] = mapped_column(String(8), nullable=False)  # POSTED | PENDING
    balance_centavos: Mapped[int | None] = mapped_column(BigInteger)

    # Categorização (§4.5): sugestão do Pluggy + override local (nossa fonte de verdade).
    categoria_pluggy_id: Mapped[str | None] = mapped_column(
        ForeignKey("categoria.pluggy_id", ondelete="SET NULL"), index=True
    )
    categoria_override_id: Mapped[str | None] = mapped_column(
        ForeignKey("categoria.pluggy_id", ondelete="SET NULL"), index=True
    )
    categoria_ajustada_usuario: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Merchant / operação.
    merchant_cnpj: Mapped[str | None] = mapped_column(String(20))
    merchant_cnae: Mapped[str | None] = mapped_column(String(20))
    merchant_nome: Mapped[str | None] = mapped_column(String(255))
    merchant_categoria: Mapped[str | None] = mapped_column(String(255))
    operation_type: Mapped[str | None] = mapped_column(String(64))
    provider_code: Mapped[str | None] = mapped_column(String(64))
    provider_id: Mapped[str | None] = mapped_column(String(64))
    ordem: Mapped[int | None] = mapped_column(Integer)

    # Metadados de cartão → competência (§4.2).
    bill_id: Mapped[int | None] = mapped_column(
        ForeignKey("fatura.id", ondelete="SET NULL"), index=True
    )
    installment_number: Mapped[int | None] = mapped_column(Integer)
    total_installments: Mapped[int | None] = mapped_column(Integer)
    total_amount_centavos: Mapped[int | None] = mapped_column(BigInteger)
    payee_mcc: Mapped[int | None] = mapped_column(Integer)

    # Flags do usuário (§4.3/§4.4).
    eh_transferencia: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    revisada: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Texto do usuário (§4.5): `description` é do Pluggy e reescrito a cada sync, então a descrição
    # própria e as observações moram em colunas separadas (protegidas por CAMPOS_USUARIO).
    descricao_usuario: Mapped[str | None] = mapped_column(String(255))
    observacoes: Mapped[str | None] = mapped_column(Text)
    contraparte_id: Mapped[int | None] = mapped_column(
        ForeignKey("transacao.id", ondelete="SET NULL"), index=True
    )
    transferencia_origem: Mapped[str | None] = mapped_column(String(8))  # auto | manual
    # Vínculo com uma assinatura (§4.7): manual (drawer) ou automático (match por nome no sync).
    assinatura_id: Mapped[int | None] = mapped_column(
        ForeignKey("assinatura.id", ondelete="SET NULL"), index=True
    )
    # Usuário marcou "não é assinatura" → detecção e sugestões ignoram esta transação (§4.7).
    nao_e_assinatura: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Vínculo com um provento de investimento (§4.9): o crédito na conta que É o dividendo do FII
    # (INTEREST). Manual, com sugestão por valor+data. Escopo pelo pai (`investimento`).
    investimento_transacao_id: Mapped[int | None] = mapped_column(
        ForeignKey("investimento_transacao.id", ondelete="SET NULL"), index=True
    )

    pluggy_criado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pluggy_atualizado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TransacaoPagamento(Base):
    """1:1 com transacao (só em transferências/pagamentos) — `transactions.paymentData`."""

    __tablename__ = "transacao_pagamento"

    transacao_id: Mapped[int] = mapped_column(
        ForeignKey("transacao.id", ondelete="CASCADE"), primary_key=True
    )
    metodo: Mapped[str | None] = mapped_column(String(16))  # PIX|TED|DOC|BOLETO
    reason: Mapped[str | None] = mapped_column(String(255))
    reference_number: Mapped[str | None] = mapped_column(String(64))
    receiver_reference_id: Mapped[str | None] = mapped_column(String(64))

    payer_nome: Mapped[str | None] = mapped_column(String(255))
    payer_conta: Mapped[str | None] = mapped_column(String(64))
    payer_agencia: Mapped[str | None] = mapped_column(String(32))
    payer_doc_tipo: Mapped[str | None] = mapped_column(String(8))  # CPF|CNPJ
    payer_doc_valor: Mapped[str | None] = mapped_column(String(32))

    receiver_nome: Mapped[str | None] = mapped_column(String(255))
    receiver_conta: Mapped[str | None] = mapped_column(String(64))
    receiver_agencia: Mapped[str | None] = mapped_column(String(32))
    receiver_doc_tipo: Mapped[str | None] = mapped_column(String(8))
    receiver_doc_valor: Mapped[str | None] = mapped_column(String(32))

    boleto_base_amount_centavos: Mapped[int | None] = mapped_column(BigInteger)
    boleto_interest_centavos: Mapped[int | None] = mapped_column(BigInteger)
    boleto_discount_centavos: Mapped[int | None] = mapped_column(BigInteger)
    boleto_penalty_centavos: Mapped[int | None] = mapped_column(BigInteger)
