"""Fila de revisão de transações (§4.3) — fonte única da regra de "está pendente?".

O usuário escolhe uma data de corte (`usuario.revisao_desde`). Transação **anterior** a ela tem a
revisão *ignorada*: sai da contagem e do filtro de pendentes, mas **não** é marcada como revisada —
`transacao.revisada` continua sendo o dado cru, escrito só pelo próprio usuário. Por isso "pendente"
é derivado aqui, e não uma coluna: mudar ou limpar a data de corte tem efeito imediato e reversível,
sem migration de dados.

O corte é **inclusivo**: a data escolhida já pede revisão.
"""

from datetime import date, datetime

from sqlalchemy import ColumnElement, and_

from app.models.transacao import Transacao
from app.services.periodo import limites_sp


def corte_revisao(revisao_desde: date | None) -> datetime | None:
    """Data de corte do usuário → instante UTC comparável com `transacao.date`. None = sem corte."""
    return None if revisao_desde is None else limites_sp(revisao_desde, revisao_desde)[0]


def expr_pendente_revisao(corte: datetime | None) -> ColumnElement[bool]:
    """Predicado SQL de "está na fila de revisão": não revisada e a partir do corte."""
    pendente = Transacao.revisada.is_(False)
    if corte is None:
        return pendente
    return and_(pendente, Transacao.date >= corte)
