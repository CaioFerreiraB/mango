"""Busca de usuários da instância (§4.11 — "com quem" dividir/convidar).

Sem filtro por posse (não é entidade user-owned): qualquer usuário autenticado pode buscar
qualquer outro da mesma instância, com campos mínimos — é o único jeito de montar a lista de
"com quem dividir" no modo self-hosted.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.usuario import Usuario
from app.schemas.usuario import UsuarioBusca
from app.security.current_user import get_current_user

router = APIRouter(prefix="/usuarios", tags=["usuario"])

_LIMITE_BUSCA = 20


@router.get("/buscar", response_model=list[UsuarioBusca])
def buscar(
    q: str = Query(default="", max_length=255),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    query = select(Usuario).where(Usuario.id != user.id)
    termo = q.strip()
    if termo:
        padrao = f"%{termo}%"
        query = query.where(or_(Usuario.nome.ilike(padrao), Usuario.email.ilike(padrao)))
    usuarios = db.scalars(query.order_by(Usuario.nome).limit(_LIMITE_BUSCA)).all()
    return [
        UsuarioBusca(
            id=u.id,
            nome=u.nome,
            avatar=u.avatar,
            status="usuario" if u.senha_hash else "so_divisao",
        )
        for u in usuarios
    ]
