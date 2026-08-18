"""Router de `configuracao_sistema` (§4.11-otimização). Leitura aberta a qualquer usuário
autenticado (o módulo de divisão precisa saber se está "otimizado" pra render correto, inclusive
contas `tipo="divisao"`); escrita restrita ao dono da instância (`require_admin`, mesmo padrão de
`app/routers/admin_usuarios.py` — 404 fora do self-hosted, 403 se não-admin).
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.usuario import Usuario
from app.schemas.configuracao import ConfiguracaoSistemaRead, ConfiguracaoSistemaUpdate
from app.security.current_user import get_current_user, require_admin
from app.services import configuracao as configuracao_service

router = APIRouter(prefix="/configuracao-sistema", tags=["configuracao_sistema"])


@router.get("", response_model=ConfiguracaoSistemaRead)
def obter(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    return configuracao_service.obter(db)


@router.patch("", response_model=ConfiguracaoSistemaRead)
def atualizar(
    payload: ConfiguracaoSistemaUpdate,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(require_admin),
):
    return configuracao_service.atualizar(db, payload)
