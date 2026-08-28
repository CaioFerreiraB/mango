"""Regras de transferência e pagamento de fatura (§4.2/§4.4). Roda após o sync.

Duas responsabilidades, ambas respeitando o override do usuário (`transferencia_origem
== "manual"` nunca é tocado — S3/§4.4):

1. **Pagamento de fatura (05100000):** débito na conta corrente categorizado como
   "Pagamento de cartão de crédito" é caixa, não competência → marca `eh_transferencia`
   para não recontabilizar o gasto (que já entra pela fatura do cartão, §4.2).
2. **Pareamento de duas pernas:** transferência entre duas contas do próprio usuário
   (ambas conectadas) aparece como duas transações. Casa saída↔entrada por valor oposto,
   data próxima e contas distintas, com sinal forte de "mesma titularidade" (categoria
   04xxxxxx) ou documento igual no `paymentData`. Liga as pernas por `contraparte_id` e
   marca ambas como transferência. Sem contraparte → perna única, transação comum.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.categoria import CATEGORIA_PAGAMENTO_FATURA, PREFIXO_MESMA_TITULARIDADE
from app.models.transacao import Transacao, TransacaoPagamento
from app.repositories.transacao import TransacaoRepository


def aplicar_regras_transferencia(
    db: Session, usuario_id: int, *, desde: date | None = None
) -> None:
    repo = TransacaoRepository(db, usuario_id)
    txs = _carregar(db, usuario_id, desde)
    _detectar_pagamento_fatura(repo, txs)
    _parear_transferencias(db, repo, txs)


def _carregar(db: Session, usuario_id: int, desde: date | None) -> list[Transacao]:
    stmt = select(Transacao).where(Transacao.usuario_id == usuario_id)
    if desde is not None:
        stmt = stmt.where(Transacao.date >= datetime(desde.year, desde.month, desde.day))
    return list(db.scalars(stmt).all())


def _cat_efetiva(t: Transacao) -> str | None:
    """Categoria CRUA (manual > banco) — de propósito mais estreita que `categoria_resolucao`.

    Aqui a pergunta é "o banco/usuário disse que isto é pagamento de fatura?", e a resposta tem de
    valer no pós-sync, antes de regras e assinaturas estarem resolvidas. O filtro da listagem
    (`ocultar_pagamento_fatura`) usa a categoria EFETIVA: lá a pergunta é "isto deve sumir da tela
    agora?", e recategorizar por regra ou assinatura tem de bastar. A divergência é intencional.
    """
    return t.categoria_override_id or t.categoria_pluggy_id


def _mesma_titularidade(t: Transacao) -> bool:
    cat = _cat_efetiva(t)
    return cat is not None and cat.startswith(PREFIXO_MESMA_TITULARIDADE)


def _detectar_pagamento_fatura(repo: TransacaoRepository, txs: list[Transacao]) -> None:
    for t in txs:
        if t.transferencia_origem == "manual":
            continue
        if _cat_efetiva(t) == CATEGORIA_PAGAMENTO_FATURA and not t.eh_transferencia:
            repo.update(t, eh_transferencia=True, transferencia_origem="auto")


def _parear_transferencias(db: Session, repo: TransacaoRepository, txs: list[Transacao]) -> None:
    pagamentos = _pagamentos_por_transacao(db, [t.id for t in txs])
    candidatos = [
        t
        for t in txs
        if t.contraparte_id is None
        and t.transferencia_origem != "manual"
        and _cat_efetiva(t) != CATEGORIA_PAGAMENTO_FATURA
        and (_mesma_titularidade(t) or t.id in pagamentos)
    ]
    usados: set[int] = set()
    for i, a in enumerate(candidatos):
        if a.id in usados:
            continue
        for b in candidatos[i + 1 :]:
            if b.id in usados:
                continue
            if _par_valido(a, b, pagamentos):
                repo.update(
                    a, contraparte_id=b.id, eh_transferencia=True, transferencia_origem="auto"
                )
                repo.update(
                    b, contraparte_id=a.id, eh_transferencia=True, transferencia_origem="auto"
                )
                usados.update({a.id, b.id})
                break


def _par_valido(a: Transacao, b: Transacao, pagamentos: dict[int, TransacaoPagamento]) -> bool:
    if a.amount_centavos == 0 or a.amount_centavos != -b.amount_centavos:
        return False  # precisa ser valor oposto e não-nulo
    if a.conta_id == b.conta_id:
        return False  # duas pernas ficam em contas distintas
    if abs((a.date - b.date).total_seconds()) > settings.sync_pareamento_dias * 86400:
        return False
    if _mesma_titularidade(a) or _mesma_titularidade(b):
        return True
    return bool(_docs(pagamentos.get(a.id)) & _docs(pagamentos.get(b.id)))


def _docs(pag: TransacaoPagamento | None) -> set[str]:
    if pag is None:
        return set()
    return {d for d in (pag.payer_doc_valor, pag.receiver_doc_valor) if d}


def _pagamentos_por_transacao(db: Session, ids: list[int]) -> dict[int, TransacaoPagamento]:
    if not ids:
        return {}
    rows = db.scalars(
        select(TransacaoPagamento).where(TransacaoPagamento.transacao_id.in_(ids))
    ).all()
    return {p.transacao_id: p for p in rows}
