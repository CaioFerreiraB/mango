"""Regras de transferência e pagamento de fatura (§4.2/§4.4). Roda após o sync.

Duas responsabilidades, ambas respeitando o override do usuário (`transferencia_origem
== "manual"` nunca é tocado — S3/§4.4):

1. **Pagamento de fatura (05100000):** débito na conta corrente categorizado como
   "Pagamento de cartão de crédito" é caixa, não competência → marca `eh_transferencia`
   para não recontabilizar o gasto (que já entra pela fatura do cartão, §4.2). Se só UMA
   ponta tem essa categoria (o banco chama de boleto/PIX, ou o "pagamento recebido" do cartão
   vem sem categoria), o débito na conta BANK e o crédito no cartão de mesmo valor e data
   próxima são ligados como as duas pernas do mesmo pagamento.
2. **Pareamento de duas pernas:** transferência entre duas contas do próprio usuário
   (ambas conectadas) aparece como duas transações. Casa saída↔entrada por valor oposto,
   data próxima e contas distintas, com sinal forte de "mesma titularidade" (categoria
   04xxxxxx) ou documento igual no `paymentData`. Liga as pernas por `contraparte_id` e
   marca ambas como transferência. Sem contraparte → perna única, transação comum.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.categoria import CATEGORIA_PAGAMENTO_FATURA, PREFIXO_MESMA_TITULARIDADE
from app.models.conta import Conta
from app.models.transacao import Transacao, TransacaoPagamento
from app.repositories.transacao import TransacaoRepository


def aplicar_regras_transferencia(
    db: Session, usuario_id: int, *, desde: date | None = None
) -> None:
    repo = TransacaoRepository(db, usuario_id)
    txs = _carregar(db, usuario_id, desde)
    pagamentos = _pagamentos_por_transacao(db, [t.id for t in txs])
    _detectar_pagamento_fatura(repo, txs)
    _parear_pagamento_fatura(db, repo, usuario_id, txs, pagamentos)
    _parear_transferencias(repo, txs, pagamentos)


def _carregar(db: Session, usuario_id: int, desde: date | None) -> list[Transacao]:
    """Transações a partir de `desde` menos a tolerância do pareamento: a outra perna de uma
    transação da janela pode ser até `sync_pareamento_dias` anterior ao corte."""
    stmt = select(Transacao).where(Transacao.usuario_id == usuario_id)
    if desde is not None:
        corte = datetime(desde.year, desde.month, desde.day)
        stmt = stmt.where(Transacao.date >= corte - timedelta(days=settings.sync_pareamento_dias))
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


def _parear_pagamento_fatura(
    db: Session,
    repo: TransacaoRepository,
    usuario_id: int,
    txs: list[Transacao],
    pagamentos: dict[int, TransacaoPagamento],
) -> None:
    """Débito BANK ↔ crédito no cartão (CREDIT) de mesmo valor, data próxima, com ao menos uma
    ponta categorizada como pagamento de fatura. Valor em módulo: o sinal do `amount` no cartão
    vem invertido em relação ao banco, dependendo do conector.

    Débito com par válido entre contas próprias fica para `_parear_transferencias`: senão o
    crédito da outra conta ficaria sem par e viraria receita. Sem esse par (inclusive débito de
    fatura que o banco categorizou como mesma titularidade), o cartão é a contraparte."""
    tipos = dict(
        db.execute(select(Conta.id, Conta.type).where(Conta.usuario_id == usuario_id)).all()
    )

    def livres(tipo_conta: str, tipo_tx: str) -> list[Transacao]:
        return [
            t
            for t in txs
            if tipos.get(t.conta_id) == tipo_conta
            and t.type == tipo_tx
            and t.contraparte_id is None
            and t.transferencia_origem != "manual"
            and t.amount_centavos != 0
        ]

    cartao = livres("CREDIT", "CREDIT")
    proprias = _candidatos_proprios(txs, pagamentos)
    janela = settings.sync_pareamento_dias * 86400
    for deb in livres("BANK", "DEBIT"):
        if deb in proprias and any(_par_valido(deb, b, pagamentos) for b in proprias):
            continue  # `_par_valido` recusa a própria transação (mesma conta)
        for cre in cartao:
            if (
                abs(deb.amount_centavos) == abs(cre.amount_centavos)
                and abs((deb.date - cre.date).total_seconds()) <= janela
                and CATEGORIA_PAGAMENTO_FATURA in (_cat_efetiva(deb), _cat_efetiva(cre))
            ):
                for a, b in ((deb, cre), (cre, deb)):
                    repo.update(
                        a, contraparte_id=b.id, eh_transferencia=True, transferencia_origem="auto"
                    )
                cartao.remove(cre)
                break


def _candidatos_proprios(
    txs: list[Transacao], pagamentos: dict[int, TransacaoPagamento]
) -> list[Transacao]:
    """Pernas possíveis de transferência entre contas próprias ainda sem par."""
    return [
        t
        for t in txs
        if t.contraparte_id is None
        and t.transferencia_origem != "manual"
        and _cat_efetiva(t) != CATEGORIA_PAGAMENTO_FATURA
        and (_mesma_titularidade(t) or t.id in pagamentos)
    ]


def _parear_transferencias(
    repo: TransacaoRepository, txs: list[Transacao], pagamentos: dict[int, TransacaoPagamento]
) -> None:
    candidatos = _candidatos_proprios(txs, pagamentos)
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
