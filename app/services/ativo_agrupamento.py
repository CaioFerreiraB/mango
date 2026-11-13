"""Agrupa posições de renda fixa num `ativo` (§4.9, decisão do usuário). Roda após o sync,
junto do match de assinaturas.

Idempotente: só preenche `ativo_id` NULL — nunca desfaz um agrupamento manual (que sobrevive ao
re-sync via pop no upsert). Chave = ISIN (mais preciso) senão nome normalizado, então "Tesouro
Selic 2028" junta suas N compras já no 1º sync. Dois papéis distintos com a mesma chave juntam por
engano → o split é manual (ponytail: sem forma automática de distinguir CDBs de nome igual).

Chave dividida em vários ativos (o usuário separou à mão — caso das caixinhas do Nubank, que
chegam todas como "CDB - NU FINANCEIRA…", uma posição por aporte, sem o nome da caixinha): a
compra nova vai p/ o ativo de um aporte "recorrente" igual (mesma taxa, mesmo valor aplicado, mesmo
dia do mês — o depósito agendado), senão p/ a "caixa de entrada" (ativo com o nome cru do Pluggy,
recriado se preciso) p/ o usuário classificar. A caixa de entrada vazia (todas as compras movidas)
também conta como split; apagá-la faz a chave voltar a se comportar como um grupo renomeado.
ponytail: recorrência é heurística; aporte avulso sempre cai na caixa de entrada — o teto é o split
manual.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ativo import Ativo
from app.models.investimento import Investimento
from app.repositories.ativo import AtivoRepository
from app.services.assinatura_deteccao import normalizar_nome

RENDA_FIXA = ("FIXED_INCOME",)


def _chave(inv: Investimento) -> str | None:
    if inv.isin:
        return f"isin:{inv.isin}"
    nome = normalizar_nome(inv.nome)
    return f"nome:{nome}" if nome else None


def _recorrencia(inv: Investimento) -> tuple | None:
    """Assinatura de aporte agendado: taxa + valor aplicado + dia do mês da aplicação."""
    if inv.purchase_date is None or inv.amount_original_centavos is None:
        return None
    return (inv.rate, inv.amount_original_centavos, inv.purchase_date.day)


def agrupar_renda_fixa(db: Session, usuario_id: int) -> None:
    posicoes = db.scalars(
        select(Investimento)
        .where(Investimento.usuario_id == usuario_id, Investimento.type.in_(RENDA_FIXA))
        .order_by(Investimento.id)
    ).all()
    nomes = {a.id: a.nome for a in db.scalars(select(Ativo).where(Ativo.usuario_id == usuario_id))}
    por_chave: dict[str, set[int]] = {}  # chave → ativos que já têm compras dela
    recorrentes: dict[tuple, int] = {}  # (chave, recorrência) → ativo (a compra mais nova vence)

    def _registrar(inv: Investimento, chave: str) -> None:
        por_chave.setdefault(chave, set()).add(inv.ativo_id)
        if (rec := _recorrencia(inv)) is not None:
            recorrentes[(chave, rec)] = inv.ativo_id

    for inv in posicoes:
        if inv.ativo_id is not None and (chave := _chave(inv)) is not None:
            _registrar(inv, chave)

    repo = AtivoRepository(db, usuario_id)
    for inv in (p for p in posicoes if p.ativo_id is None):
        chave = _chave(inv)
        if chave is None:
            continue  # sem ISIN nem nome → fica avulso (mostrado como ativo próprio no resumo)
        ids = por_chave.get(chave, set())
        nome = inv.nome or "Renda fixa"
        # Caixa de entrada = ativo com o nome cru, mesmo vazio: se o usuário moveu TODAS as compras
        # para uma caixinha, ela continua existindo e sinaliza o split (≠ só renomear o grupo).
        entrada = next((i for i in sorted(nomes) if nomes[i] == nome), None)
        if len(ids) == 1 and entrada in (None, *ids):
            ativo_id = next(iter(ids))  # chave num ativo só (inclusive renomeado inteiro)
        else:
            rec = _recorrencia(inv)
            ativo_id = recorrentes.get((chave, rec)) if rec is not None else None
            if ativo_id is None:
                ativo_id = entrada
                if ativo_id is None:
                    ativo_id = repo.create(nome=nome).id
                    nomes[ativo_id] = nome
        inv.ativo_id = ativo_id
        _registrar(inv, chave)
    db.commit()
