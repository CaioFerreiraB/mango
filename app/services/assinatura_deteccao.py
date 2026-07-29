"""Detecção automática de assinaturas (§4.7).

O Pluggy não expõe flag de recorrência (confirmado na descoberta), então inferimos por
heurística sobre as transações: mesmo estabelecimento, valor estável e cadência regular. A
função `candidatos(...)` é **pura** (desacoplada do ORM) para ser testável; `candidatos_novos(...)`
lê as transações e devolve os candidatos que ainda não viraram assinatura.

A detecção **não persiste** e **não roda no sync**: o usuário dispara a busca pelo botão e confirma,
via switches, quais candidatos adicionar (marcados `detectada_automaticamente`).

Dedup por nome normalizado + aliases (`nomes_transacao`) das assinaturas existentes, então renomear
uma assinatura não faz a busca re-sugeri-la (§4.7).
"""

from __future__ import annotations

import statistics
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.transacao import Transacao
from app.repositories.assinatura import AssinaturaRepository

# (dias_min, dias_max, periodicidade) — gap mediano entre ocorrências → periodicidade.
_BUCKETS = (
    (24, 37, "mensal"),
    (75, 100, "trimestral"),
    (160, 200, "semestral"),
    (330, 400, "anual"),
)


@dataclass(frozen=True)
class TxAssinatura:
    """Subconjunto de `transacao` usado pela detecção (desacopla do ORM para teste)."""

    date: datetime
    type: str  # DEBIT | CREDIT
    amount_centavos: int  # negativo para DEBIT, na moeda de `currency_code`
    amount_in_account_currency_centavos: int | None  # valor em reais (compra internacional)
    currency_code: str
    eh_transferencia: bool
    total_installments: int | None
    merchant_cnpj: str | None
    merchant_nome: str | None
    description: str | None
    categoria_id: str | None  # categoria efetiva (override senão sugestão)
    conta_id: int | None
    id: int = 0  # id da transacao (dialog marca "não é assinatura"); default preserva os testes


@dataclass(frozen=True)
class Candidato:
    nome: str
    valor_centavos: int  # mediana em reais (valor efetivo na conta)
    moeda: str  # currency_code predominante
    valor_moeda_centavos: int | None  # mediana na moeda estrangeira, só quando moeda != BRL
    periodicidade: str
    categoria_id: str | None
    conta_id: int | None
    data_inicio: date
    ocorrencias: int
    transacao_ids: tuple[int, ...] = ()  # ids das transações do grupo (marcar "não é assinatura")


def normalizar_nome(nome: str | None) -> str:
    return " ".join((nome or "").strip().lower().split())


def _valor_reais(tx: TxAssinatura) -> int:
    """Valor efetivo em reais: o convertido na conta (internacional) senão o `amount` cru."""
    return tx.amount_in_account_currency_centavos or tx.amount_centavos


def _chave(tx: TxAssinatura) -> str | None:
    """Agrupa por estabelecimento: CNPJ quando houver, senão nome/descrição normalizados."""
    if tx.merchant_cnpj:
        return f"cnpj:{tx.merchant_cnpj}"
    base = normalizar_nome(tx.merchant_nome or tx.description)
    return f"nome:{base}" if base else None


def _moda(valores: list) -> object | None:
    return Counter(valores).most_common(1)[0][0] if valores else None


def candidatos(
    transacoes: list[TxAssinatura],
    *,
    min_ocorrencias: int | None = None,
    tolerancia_valor: float | None = None,
) -> list[Candidato]:
    """Grupos de transações que parecem assinaturas. Exclui transferências e parcelamentos."""
    min_ocorrencias = min_ocorrencias or settings.assinatura_min_ocorrencias
    if tolerancia_valor is None:
        tolerancia_valor = settings.assinatura_tolerancia_valor

    grupos: dict[str, list[TxAssinatura]] = {}
    for tx in transacoes:
        if tx.type != "DEBIT" or tx.eh_transferencia:
            continue
        if tx.total_installments and tx.total_installments > 1:
            continue  # parcelamento não é assinatura
        chave = _chave(tx)
        if chave is not None:
            grupos.setdefault(chave, []).append(tx)

    resultado: list[Candidato] = []
    for txs in grupos.values():
        if len(txs) < min_ocorrencias:
            continue
        txs_ord = sorted(txs, key=lambda t: t.date)
        # Estabilidade no valor nativo (preço em moeda estrangeira é mais estável que o convertido).
        valores = [abs(t.amount_centavos) for t in txs_ord]
        mediana = int(statistics.median(valores))
        if mediana <= 0 or any(abs(v - mediana) > tolerancia_valor * mediana for v in valores):
            continue  # valores dispersos → provavelmente não é assinatura

        dias = [(b.date - a.date).days for a, b in zip(txs_ord, txs_ord[1:], strict=False)]
        gap = statistics.median(dias) if dias else 0
        periodicidade = next((p for lo, hi, p in _BUCKETS if lo <= gap <= hi), None)
        if periodicidade is None:
            continue  # sem cadência reconhecível

        moeda = _moda([t.currency_code for t in txs_ord]) or "BRL"
        valor_reais = int(statistics.median([abs(_valor_reais(t)) for t in txs_ord]))
        resultado.append(
            Candidato(
                nome=(txs_ord[-1].merchant_nome or txs_ord[-1].description or "Assinatura").strip(),
                valor_centavos=valor_reais,
                moeda=moeda,
                valor_moeda_centavos=mediana if moeda != "BRL" else None,
                periodicidade=periodicidade,
                categoria_id=_moda([t.categoria_id for t in txs_ord if t.categoria_id]),
                conta_id=_moda([t.conta_id for t in txs_ord if t.conta_id is not None]),
                data_inicio=txs_ord[0].date.date(),
                ocorrencias=len(txs_ord),
                transacao_ids=tuple(t.id for t in txs_ord),
            )
        )
    return resultado


def candidatos_novos(db: Session, usuario_id: int) -> list[Candidato]:
    """Assinaturas candidatas detectadas nas transações do usuário que ainda não existem como
    assinatura (dedup por nome normalizado). Escopado por usuário (§5.2). Só lê — quem confirma e
    cria é o usuário, pelo dialog de busca (o sync não persiste mais)."""
    txs = db.scalars(
        select(Transacao).where(
            Transacao.usuario_id == usuario_id,
            Transacao.type == "DEBIT",
            Transacao.eh_transferencia.is_(False),
            Transacao.nao_e_assinatura.is_(False),
        )
    ).all()
    entradas = [
        TxAssinatura(
            id=t.id,
            date=t.date,
            type=t.type,
            amount_centavos=t.amount_centavos,
            amount_in_account_currency_centavos=t.amount_in_account_currency_centavos,
            currency_code=t.currency_code,
            eh_transferencia=t.eh_transferencia,
            total_installments=t.total_installments,
            merchant_cnpj=t.merchant_cnpj,
            merchant_nome=t.merchant_nome,
            description=t.description,
            categoria_id=t.categoria_override_id or t.categoria_pluggy_id,
            conta_id=t.conta_id,
        )
        for t in txs
    ]

    # Dedup contra o rótulo E os aliases (nomes_transacao) das assinaturas já existentes — assim
    # renomear a assinatura não faz a busca re-sugerir a mesma cobrança (§4.7).
    vistos: set[str] = set()
    for a in AssinaturaRepository(db, usuario_id).list():
        vistos.add(normalizar_nome(a.nome))
        vistos.update(normalizar_nome(n) for n in a.nomes_transacao)
    novos: list[Candidato] = []
    for c in candidatos(entradas):
        chave = normalizar_nome(c.nome)
        if chave in vistos:
            continue
        vistos.add(chave)
        novos.append(c)
    return novos
