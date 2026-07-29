"""Router manual de assinatura: só a visão agregada `/assinaturas/resumo` (§4.7). O CRUD
segue na factory (`app/routers/__init__.py`). Este router é registrado ANTES do factory para
`/resumo` não colidir com `/{item_id}`."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.usuario import Usuario
from app.schemas.assinatura import AssinaturaCandidatoRead, AssinaturaResumoRead
from app.security.current_user import get_current_user
from app.services import assinatura as assinatura_service
from app.services import assinatura_deteccao

router = APIRouter(prefix="/assinaturas", tags=["assinatura"])


@router.get("/resumo", response_model=AssinaturaResumoRead)
def resumo(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    return assinatura_service.resumo(db, user.id)


@router.get("/candidatos", response_model=list[AssinaturaCandidatoRead])
def candidatos(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    """Busca sob demanda: assinaturas candidatas detectadas nas transações que ainda não existem.
    Só lê — o usuário confirma e cria pelo dialog (§4.7)."""
    return assinatura_deteccao.candidatos_novos(db, user.id)
