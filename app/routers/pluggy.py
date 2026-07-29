"""Endpoints auxiliares do Pluggy que não mapeiam 1:1 a uma tabela.

`GET /pluggy/connectores` — catálogo de instituições para o seletor de vínculo manual da conta.
Prefixo próprio (não `/instituicoes`) para não colidir com o factory read-only.
"""

from fastapi import APIRouter, Depends

from app.models.usuario import Usuario
from app.schemas.pluggy import ConnectorRead
from app.security.current_user import get_current_user
from app.services import conta as conta_service

router = APIRouter(prefix="/pluggy", tags=["pluggy"])


@router.get("/connectores", response_model=list[ConnectorRead])
def listar_connectores(
    nome: str | None = None,
    user: Usuario = Depends(get_current_user),  # protegido (não expor sem auth)
) -> list[ConnectorRead]:
    return conta_service.listar_connectores(nome)
