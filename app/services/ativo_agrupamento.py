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

from collections.abc import Iterable

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.atomic import atomica
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
    # Uma transação só (o `repo.create` do meio não commita → não solta as travas) e ativos
    # travados ANTES de ler/gravar compras: mesma ordem ativos → compras do PATCH e do vínculo.
    with atomica(db):
        travar_ativos(db, usuario_id, None)
        _agrupar(db, usuario_id)
        db.flush()
        sincronizar_objetivos_ativos(db, usuario_id)  # compra nova herda o objetivo do ativo


def _agrupar(db: Session, usuario_id: int) -> None:
    posicoes = db.scalars(
        select(Investimento)
        .where(Investimento.usuario_id == usuario_id, Investimento.type.in_(RENDA_FIXA))
        .order_by(Investimento.id)
        .execution_options(populate_existing=True)  # estado pós-trava, não o do identity map
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


def travar_ativos(db: Session, usuario_id: int, ativo_ids: Iterable[int] | None) -> list[int]:
    """`FOR NO KEY UPDATE` nos ativos (None = todos do usuário), em ordem de id. Ordem de travas
    comum a todos os fluxos: ativos antes das compras — quem mexe numa compra (mover de ativo)
    trava origem e destino antes, senão cruza com um vínculo/sync que já travou os ativos e espera
    pela compra (deadlock). No SQLite é no-op (sem FOR UPDATE)."""
    consulta = select(Ativo.id).where(Ativo.usuario_id == usuario_id)
    if ativo_ids is not None:
        consulta = consulta.where(Ativo.id.in_({i for i in ativo_ids if i is not None}))
    return list(db.scalars(consulta.order_by(Ativo.id).with_for_update(key_share=True)).all())


def sincronizar_objetivos_ativos(
    db: Session, usuario_id: int, ativo_ids: Iterable[int] | None = None
) -> None:
    """Espelha `ativo.objetivo_id` (fonte da verdade) nas compras dos ativos dados (None = todos do
    usuário). Chamar após qualquer escrita de `ativo_id` ou de vínculo; não faz commit.

    Trava os ativos (ordem de id) antes do UPDATE: em Read Committed cada instrução tira snapshot
    novo, então o espelho grava o `objetivo_id` confirmado por um vínculo concorrente do mesmo ativo
    em vez de regravar o valor antigo. `FOR NO KEY UPDATE` (não `FOR UPDATE`): é o mesmo lock que o
    UPDATE de `ativo` do vínculo pega, e não conflita com o `KEY SHARE` que a FK põe no ativo quando
    uma compra é movida para ele — com `FOR UPDATE`, mover + vincular em paralelo dava deadlock.
    Escopo restrito aos ativos afetados → vínculos de ativos diferentes não disputam as compras."""
    ids = travar_ativos(db, usuario_id, ativo_ids)
    if not ids:
        return
    db.execute(
        update(Investimento)
        .where(Investimento.usuario_id == usuario_id, Investimento.ativo_id.in_(ids))
        .values(
            objetivo_id=select(Ativo.objetivo_id)
            .where(Ativo.id == Investimento.ativo_id, Ativo.usuario_id == usuario_id)
            .scalar_subquery()
        )
        .execution_options(synchronize_session=False)
    )
