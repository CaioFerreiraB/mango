"""Agrupamento das parcelas de uma mesma compra (§4.5).

O Pluggy NÃO expõe id de compra: `creditCardMetadata` traz `billId`, `installmentNumber`,
`totalInstallments`, `totalAmount` e `payeeMCC`, e nada que ligue as N parcelas entre si
(docs/dev/descoberta-pluggy.md). Então a chave é derivada — conta + estabelecimento + nº de
parcelas + valor total + **mês da compra inferido**.

A âncora de mês é o que impede duas compras idênticas no mesmo lugar, em meses diferentes, de
caírem no mesmo grupo: a parcela k foi lançada k−1 meses depois da compra, então voltar esse
deslocamento devolve o mês de origem, igual para todas as parcelas de uma compra e diferente
entre compras distintas.

Na prática o cartão não manda `merchant_nome`, `merchant_cnpj` nem `totalAmount` — sobra a
descrição, e ela NÃO é constante entre as parcelas: traz o contador ("Decolar Com 1/6") e às vezes
troca de forma no meio da compra ("DECOLAR COM LTDA 5/6"). Por isso a chave passa por
`_estabelecimento`, que tira esses dois pedaços antes de comparar; sem isso cada parcela ganhava
uma chave própria e o agrupamento não formava grupo nenhum.

Sem coluna persistida: a chave é função pura de colunas que já existem, e materializá-la custaria
migration, backfill e risco de dado obsoleto por um caminho que roda uma vez por clique.
"""

from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.transacao import Transacao
from app.services.texto import normalizar_texto

# O contador de parcela vem DENTRO da descrição ("Decolar Com 1/6", "Shoppingdefilhote 10/10"):
# é o campo que mais varia entre parcelas da mesma compra e, sem remover, cada parcela ganharia
# uma chave própria — o grupo nunca se formava. Só no fim da string: "Shopee *Loja 1/2" tem o
# marcador no fim, mas um nome que contenha "24/7" no meio não é contador.
_MARCADOR_PARCELA = re.compile(r"\s*\d{1,3}\s*/\s*\d{1,3}\s*$")

# Sufixo societário: o mesmo estabelecimento aparece ora com ele, ora sem ("Decolar Com 1/6" e
# "DECOLAR COM LTDA 5/6" são a MESMA compra). Só no fim, e repetível ("... comercio ltda me").
_SUFIXO_SOCIETARIO = re.compile(r"(?:\s+(?:ltda|s\s*/?\s*a|sa|eireli|epp|mei|me))+$")


class _Parcela:
    """Campos que `chave_compra` lê (documental — `Transacao` já os tem)."""

    conta_id: int
    date: datetime
    description: str | None
    merchant_cnpj: str | None
    merchant_nome: str | None
    installment_number: int | None
    total_installments: int | None
    total_amount_centavos: int | None


def _estabelecimento(tx: _Parcela) -> str:
    """Identidade do estabelecimento, estável entre as parcelas de uma compra.

    CNPJ quando houver (estável); senão o texto normalizado — mesma escolha de
    `assinatura_deteccao._chave`. Mas o texto real é a descrição do cartão, que muda de parcela
    para parcela: nela vêm o contador ("1/6") e, às vezes, o sufixo societário. Os dois saem.
    """
    if tx.merchant_cnpj:
        return tx.merchant_cnpj
    texto = normalizar_texto(tx.merchant_nome or tx.description)
    texto = _SUFIXO_SOCIETARIO.sub("", _MARCADOR_PARCELA.sub("", texto))
    return " ".join(texto.split())


def _ancora_da_compra(data: datetime, parcela: int | None) -> str:
    """Mês da compra = mês do lançamento − (parcela − 1). Aritmética em meses absolutos para
    não depender de dateutil nem errar na virada de ano."""
    meses = data.year * 12 + (data.month - 1) - ((parcela or 1) - 1)
    return f"{meses // 12:04d}-{meses % 12 + 1:02d}"


def chave_compra(tx: _Parcela) -> str | None:
    """Identidade da compra parcelada, ou None se a transação não é parcelada.

    PURA — é o que permite testar o agrupamento sem banco.
    """
    if not tx.total_installments or tx.total_installments <= 1:
        return None
    estabelecimento = _estabelecimento(tx)
    # Sem como identificar o estabelecimento, não agrupa: agrupar errado alteraria a categoria de
    # transações que não são da mesma compra.
    if not estabelecimento:
        return None
    return "|".join(
        (
            str(tx.conta_id),
            estabelecimento,
            str(tx.total_installments),
            str(tx.total_amount_centavos),
            _ancora_da_compra(tx.date, tx.installment_number),
        )
    )


def irmas_da_compra(db: Session, usuario_id: int, tx: Transacao) -> list[Transacao]:
    """As OUTRAS parcelas da mesma compra. Lista vazia se `tx` não é parcelada."""
    chave = chave_compra(tx)
    if chave is None:
        return []
    # Pré-filtro no banco pelo que é indexado/barato (conta + nº de parcelas); o resto da chave
    # (estabelecimento, valor total, âncora) confere em Python sobre um conjunto pequeno.
    candidatas = db.scalars(
        select(Transacao).where(
            Transacao.usuario_id == usuario_id,
            Transacao.conta_id == tx.conta_id,
            Transacao.total_installments == tx.total_installments,
            Transacao.id != tx.id,
        )
    ).all()
    return [c for c in candidatas if chave_compra(c) == chave]
