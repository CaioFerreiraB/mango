"""Categoria efetiva de uma transação — precedência ÚNICA do sistema (§4.5).

    1. assinatura  — a transação é cobrança de uma assinatura → a categoria dela manda (e a
                     edição é bloqueada no PATCH: duas cobranças da mesma assinatura em
                     categorias diferentes é incoerência, não flexibilidade);
    2. manual      — `categoria_override_id`, o ajuste que o usuário fez NESTA transação. Fica
                     acima da regra para que uma regra criada depois não desfaça a correção;
    3. regra       — `categoria_regra_id`, materializado por `categoria_regras`;
    4. banco       — a sugestão do Pluggy, **se** a categoria estiver ativa para este usuário;
    5. desconhecida— NULL. Note que NÃO é "99999999/Outros": aquela é uma categoria real do
                     Pluggy, que o usuário pode usar e até desativar.

A desativação incide só sobre (4): (1)–(3) são escolhas explícitas do usuário e sobrevivem a
esconder a categoria dos seletores.

Duas formas da MESMA regra, porque os dois caminhos têm exigências diferentes:

- `expr_categoria_efetiva` (SQL) para agregação — dashboard, consumo de orçamento e o filtro da
  listagem somam/agrupam no banco, e trazer as linhas para o Python só para resolver categoria
  seria ordens de grandeza mais caro;
- `resolver` (Python) para serializar a transação, onde já temos o objeto em mãos.

`tests/test_categoria_resolucao.py` roda as duas sobre a mesma matriz e exige o mesmo resultado —
é o que impede as duas de divergirem com o tempo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models.assinatura import Assinatura
from app.models.categoria import CategoriaDesativada
from app.models.transacao import Transacao

Origem = Literal["assinatura", "manual", "regra", "banco", "desconhecida"]


# --- forma SQL (agregações) -------------------------------------------------------------


def expr_categoria_efetiva(usuario_id: int):
    """Expressão da categoria efetiva. Exige que a query tenha passado por `com_assinatura`."""
    desativadas = select(CategoriaDesativada.categoria_id).where(
        CategoriaDesativada.usuario_id == usuario_id
    )
    return func.coalesce(
        Assinatura.categoria_id,
        Transacao.categoria_override_id,
        Transacao.categoria_regra_id,
        # `categoria_desativada.categoria_id` é PK (nunca NULL), então o NOT IN não degenera.
        case((Transacao.categoria_pluggy_id.not_in(desativadas), Transacao.categoria_pluggy_id)),
    )


def com_assinatura(stmt):
    """Adiciona o outerjoin que `expr_categoria_efetiva` referencia. LEFT JOIN sobre
    `transacao.assinatura_id`, que já é indexado — e muitos-para-um, então não duplica linha.

    A query precisa ter `transacao` no FROM: selecione alguma coluna dela (o caso normal) ou use
    `select_from(Transacao)`. Selecionar SÓ a expressão não basta — o SQLAlchemy não descobre de
    onde partir e levanta `InvalidRequestError`.
    """
    return stmt.outerjoin(Assinatura, Transacao.assinatura_id == Assinatura.id)


# --- forma Python (serialização) --------------------------------------------------------


class _TemCategorias(Protocol):
    """Só o que `resolver` lê — aceita a `Transacao` do ORM e dublês de teste."""

    assinatura_id: int | None
    categoria_override_id: str | None
    categoria_regra_id: str | None
    categoria_pluggy_id: str | None


@dataclass(frozen=True)
class Contexto:
    """Estado do usuário que a resolução consulta. Carregado uma vez por página, não por linha."""

    categorias_de_assinatura: dict[int, str | None]
    desativadas: frozenset[str]


def carregar_contexto(db: Session, usuario_id: int) -> Contexto:
    """Duas consultas pequenas (assinaturas e desativadas do usuário) — evita N+1 na listagem."""
    assinaturas = db.execute(
        select(Assinatura.id, Assinatura.categoria_id).where(Assinatura.usuario_id == usuario_id)
    ).all()
    desativadas = db.scalars(
        select(CategoriaDesativada.categoria_id).where(CategoriaDesativada.usuario_id == usuario_id)
    ).all()
    return Contexto(
        categorias_de_assinatura=dict(assinaturas),
        desativadas=frozenset(desativadas),
    )


def resolver(tx: _TemCategorias, ctx: Contexto) -> tuple[str | None, Origem]:
    """Categoria efetiva + de onde ela veio (o rótulo de proveniência no drawer)."""
    if tx.assinatura_id is not None:
        categoria = ctx.categorias_de_assinatura.get(tx.assinatura_id)
        if categoria is not None:
            return categoria, "assinatura"
    if tx.categoria_override_id is not None:
        return tx.categoria_override_id, "manual"
    if tx.categoria_regra_id is not None:
        return tx.categoria_regra_id, "regra"
    if tx.categoria_pluggy_id is not None and tx.categoria_pluggy_id not in ctx.desativadas:
        return tx.categoria_pluggy_id, "banco"
    return None, "desconhecida"
