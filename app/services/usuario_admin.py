"""Gestão de usuários da instância (§4.11/§5.2) — restrita ao dono (`require_admin`).

Criar continua sendo via link de convite (`app/services/convite.py`, agora com `tipo`); aqui só
listar/ativar/desativar/excluir. Excluir é bloqueado quando o usuário tem qualquer dado vinculado
(transações, orçamentos, participações em divisão etc.) — a ação correta nesse caso é desativar.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.exceptions import ConflictError, NotFoundError
from app.models.usuario import Usuario
from app.schemas.usuario import UsuarioAdminRead
from app.security.sessions import revogar_todas

# `sessao`/`convite_usuario` são bookkeeping de acesso, não "dados" do usuário — não impedem
# exclusão. `usuario` fica de fora por ser a própria tabela (auto-FK não existe, mas por clareza).
_TABELAS_IGNORADAS_NO_CHECK_DE_EXCLUSAO = {"sessao", "convite_usuario", "usuario"}


def _para_admin_read(usuario: Usuario) -> UsuarioAdminRead:
    return UsuarioAdminRead(
        id=usuario.id,
        nome=usuario.nome,
        email=usuario.email,
        tipo=usuario.tipo,
        ativo=usuario.ativo,
        is_admin=usuario.is_admin,
        status="usuario" if usuario.senha_hash else "so_divisao",
        criado_em=usuario.criado_em,
    )


def listar_admin(db: Session) -> list[UsuarioAdminRead]:
    usuarios = db.scalars(select(Usuario).order_by(Usuario.criado_em)).all()
    return [_para_admin_read(u) for u in usuarios]


def _obter(db: Session, usuario_id: int) -> Usuario:
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise NotFoundError("usuário não encontrado")
    return usuario


def ativar(db: Session, usuario_id: int) -> UsuarioAdminRead:
    usuario = _obter(db, usuario_id)
    usuario.ativo = True
    db.commit()
    db.refresh(usuario)
    return _para_admin_read(usuario)


def desativar(db: Session, admin: Usuario, usuario_id: int) -> UsuarioAdminRead:
    if usuario_id == admin.id:
        raise ConflictError("não é possível desativar a própria conta")
    usuario = _obter(db, usuario_id)
    usuario.ativo = False
    db.commit()
    db.refresh(usuario)
    revogar_todas(db, usuario.id)  # derruba sessões vivas na hora, não espera o próximo 401
    return _para_admin_read(usuario)


def mudar_tipo(db: Session, admin: Usuario, usuario_id: int, tipo: str) -> UsuarioAdminRead:
    if usuario_id == admin.id:
        raise ConflictError("não é possível alterar o próprio tipo de acesso")
    usuario = _obter(db, usuario_id)
    if usuario.tipo == tipo:
        return _para_admin_read(usuario)  # no-op — evita revogar sessão à toa

    rebaixando = usuario.tipo == "completo" and tipo == "divisao"
    usuario.tipo = tipo
    db.commit()
    db.refresh(usuario)
    if rebaixando:
        revogar_todas(db, usuario.id)  # perde acesso a módulos que a sessão atual pode ter aberto
    return _para_admin_read(usuario)


def _possui_dados_vinculados(db: Session, usuario_id: int) -> bool:
    """True se qualquer tabela com FK p/ `usuario.id` (fora do bookkeeping de acesso) tiver
    alguma linha para este usuário. Introspecção via metadata em vez de lista hardcoded — não
    depende de lembrar de atualizar isto a cada entidade user-owned nova."""
    for table in Base.metadata.tables.values():
        if table.name in _TABELAS_IGNORADAS_NO_CHECK_DE_EXCLUSAO:
            continue
        for col in table.columns:
            for fk in col.foreign_keys:
                if fk.column.table.name != "usuario" or fk.column.name != "id":
                    continue
                existe = db.execute(
                    select(1).select_from(table).where(col == usuario_id).limit(1)
                ).first()
                if existe is not None:
                    return True
    return False


def remover(db: Session, admin: Usuario, usuario_id: int) -> None:
    if usuario_id == admin.id:
        raise ConflictError("não é possível excluir a própria conta")
    usuario = _obter(db, usuario_id)
    if _possui_dados_vinculados(db, usuario_id):
        raise ConflictError("usuário possui dados vinculados; desative a conta em vez de excluir")
    db.delete(usuario)
    db.commit()
