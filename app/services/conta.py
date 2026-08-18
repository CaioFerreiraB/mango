"""Regras de `conta`. Write do usuário: vincular a um objetivo (§4.8).

Valida que o objetivo é do MESMO usuário (isolamento) antes de vincular.

O vínculo manual de instituição é por CONEXÃO, não por conta — ver `app/services/item.py`.
"""

from sqlalchemy.orm import Session

from app.exceptions import NotFoundError
from app.models.conta import Conta
from app.repositories.conta import ContaRepository
from app.repositories.objetivo import ObjetivoRepository


def vincular_objetivo(
    db: Session, usuario_id: int, conta_id: int, objetivo_id: int | None
) -> Conta:
    contas = ContaRepository(db, usuario_id)
    conta = contas.get(conta_id)
    if conta is None:
        raise NotFoundError("conta não encontrada")

    if objetivo_id is not None:
        # Garante que o objetivo existe e pertence ao usuário (nunca de outro #4/§5.2).
        if ObjetivoRepository(db, usuario_id).get(objetivo_id) is None:
            raise NotFoundError("objetivo não encontrado")

    return contas.update(conta, objetivo_id=objetivo_id)
