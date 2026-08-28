"""Router de `categoria` (§4.5): taxonomia do Pluggy (só ativação) + personalizadas (CRUD).

Regra de negócio no service (§5.2). Aqui só HTTP + escopo do usuário: `usuario_id` vem sempre da
dependency, nunca do payload.
"""

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.usuario import Usuario
from app.schemas.categoria import CategoriaCreate, CategoriaRead, CategoriaUpdate
from app.security.current_user import get_current_user
from app.services import categoria as categoria_service

router = APIRouter(prefix="/categorias", tags=["categoria"])


@router.get("", response_model=list[CategoriaRead])
def listar(
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    apenas_ativas: bool = Query(
        False,
        description="Só as ativas. O default devolve tudo com o flag `ativa` — a tela de "
        "configurações precisa das inativas, e o rótulo de uma categoria ainda referenciada "
        "por um ajuste manual continua resolvendo.",
    ),
):
    return categoria_service.listar(db, user.id, apenas_ativas=apenas_ativas)


@router.get("/{pluggy_id}", response_model=CategoriaRead)
def obter(
    pluggy_id: str = Path(max_length=16),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return categoria_service.obter(db, user.id, pluggy_id)


@router.post("", response_model=CategoriaRead, status_code=status.HTTP_201_CREATED)
def criar(
    payload: CategoriaCreate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return categoria_service.criar(db, user.id, payload.nome, payload.icone)


@router.patch("/{pluggy_id}", response_model=CategoriaRead)
def atualizar(
    payload: CategoriaUpdate,
    pluggy_id: str = Path(max_length=16),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return categoria_service.atualizar(
        db, user.id, pluggy_id, nome=payload.nome, icone=payload.icone, ativa=payload.ativa
    )


@router.delete("/{pluggy_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover(
    pluggy_id: str = Path(max_length=16),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    categoria_service.remover(db, user.id, pluggy_id)
