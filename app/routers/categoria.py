"""Router de `categoria` — referência global read-only (sem filtro por usuário, §4.5)."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.categoria import Categoria
from app.repositories.categoria import CategoriaRepository
from app.schemas.auto import read_model
from app.security.current_user import get_current_user

CategoriaRead = read_model(Categoria)

router = APIRouter(
    prefix="/categorias", tags=["categoria"], dependencies=[Depends(get_current_user)]
)


@router.get("", response_model=list[CategoriaRead])
def listar(db: Session = Depends(get_db)):
    return CategoriaRepository(db).list()


@router.get("/{pluggy_id}", response_model=CategoriaRead)
def obter(pluggy_id: str, db: Session = Depends(get_db)):
    cat = CategoriaRepository(db).get(pluggy_id)
    if cat is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "categoria não encontrada")
    return cat
