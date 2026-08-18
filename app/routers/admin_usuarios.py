"""Gestão de usuários da instância (§4.11/§5.2), aba "Usuários" em Configurações — restrita ao
dono (`require_admin`, 404 no modo local / 403 se não-admin). Criar continua sendo via link de
convite (`app/services/convite.py`), só que agora escolhendo o `tipo` da conta.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.usuario import Usuario
from app.schemas.convite import ConvidarPessoaRead, ConvidarPessoaRequest
from app.schemas.usuario import MudarTipoRequest, UsuarioAdminRead
from app.security.current_user import require_admin
from app.services import convite as convite_service
from app.services import usuario_admin

router = APIRouter(prefix="/admin/usuarios", tags=["admin_usuarios"])


@router.get("", response_model=list[UsuarioAdminRead])
def listar(db: Session = Depends(get_db), admin: Usuario = Depends(require_admin)):
    return usuario_admin.listar_admin(db)


@router.post("", response_model=ConvidarPessoaRead, status_code=status.HTTP_201_CREATED)
def criar(
    payload: ConvidarPessoaRequest,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(require_admin),
):
    usuario, token = convite_service.convidar(db, admin, payload.nome, payload.email, payload.tipo)
    return ConvidarPessoaRead(usuario_id=usuario.id, link_convite=f"/convite/{token}")


@router.post("/{usuario_id}/reenviar-convite", response_model=ConvidarPessoaRead)
def reenviar_convite(
    usuario_id: int, db: Session = Depends(get_db), admin: Usuario = Depends(require_admin)
):
    usuario, token = convite_service.reenviar(db, admin, usuario_id)
    return ConvidarPessoaRead(usuario_id=usuario.id, link_convite=f"/convite/{token}")


@router.post("/{usuario_id}/tipo", response_model=UsuarioAdminRead)
def mudar_tipo(
    usuario_id: int,
    payload: MudarTipoRequest,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(require_admin),
):
    return usuario_admin.mudar_tipo(db, admin, usuario_id, payload.tipo)


@router.post("/{usuario_id}/ativar", response_model=UsuarioAdminRead)
def ativar(usuario_id: int, db: Session = Depends(get_db), admin: Usuario = Depends(require_admin)):
    return usuario_admin.ativar(db, usuario_id)


@router.post("/{usuario_id}/desativar", response_model=UsuarioAdminRead)
def desativar(
    usuario_id: int, db: Session = Depends(get_db), admin: Usuario = Depends(require_admin)
):
    return usuario_admin.desativar(db, admin, usuario_id)


@router.delete("/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover(
    usuario_id: int, db: Session = Depends(get_db), admin: Usuario = Depends(require_admin)
):
    usuario_admin.remover(db, admin, usuario_id)
