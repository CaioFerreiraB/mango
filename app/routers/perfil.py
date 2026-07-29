"""Router do perfil (§4.1): ler e editar o cadastro do próprio usuário.

Update com campos explícitos (S4) — segredos e `usuario_id` não são atingíveis por aqui.
"""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.exceptions import ConflictError
from app.models.usuario import Usuario
from app.schemas.perfil import BrapiTokenSet, BrapiTokenTeste, PerfilRead, PerfilUpdate
from app.security.current_user import get_current_user
from app.services import indicadores
from app.services.brapi import token_brapi

router = APIRouter(prefix="/perfil", tags=["perfil"])


@router.get("", response_model=PerfilRead)
def obter(user: Usuario = Depends(get_current_user)) -> Usuario:
    return user


@router.patch("", response_model=PerfilRead)
def atualizar(
    payload: PerfilUpdate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
) -> Usuario:
    campos = payload.model_dump(exclude_unset=True)
    novo_email = campos.get("email")
    if novo_email and novo_email != user.email:
        existe = db.scalars(select(Usuario).where(Usuario.email == novo_email)).first()
        if existe is not None:
            raise ConflictError("e-mail já em uso")
    # Reobtém na sessão do request para escrever com segurança (nunca confia no objeto externo).
    alvo = db.get(Usuario, user.id)
    for chave, valor in campos.items():
        setattr(alvo, chave, valor)
    db.commit()
    db.refresh(alvo)
    return alvo


# --- token brapi (§4.9): write-only, cifrado em repouso, nunca devolvido (§5.5) --------------


@router.put("/brapi-token", status_code=status.HTTP_204_NO_CONTENT)
def definir_brapi_token(
    payload: BrapiTokenSet,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
) -> None:
    alvo = db.get(Usuario, user.id)
    alvo.brapi_token_cifrado = payload.token.strip()
    db.commit()


@router.delete("/brapi-token", status_code=status.HTTP_204_NO_CONTENT)
def remover_brapi_token(
    db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)
) -> None:
    alvo = db.get(Usuario, user.id)
    alvo.brapi_token_cifrado = None
    db.commit()


@router.post("/brapi-token/testar", response_model=BrapiTokenTeste)
def testar_brapi_token(
    db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)
) -> BrapiTokenTeste:
    """Valida o token guardado contra a brapi (uma cotação curta). Só devolve o booleano."""
    token = token_brapi(db, user.id)
    if not token:
        return BrapiTokenTeste(valida=False)
    hoje = date.today()
    try:
        indicadores.precos_historicos("PETR4", hoje - timedelta(days=7), hoje, token)
        return BrapiTokenTeste(valida=True)
    except indicadores.IndicadorError:
        return BrapiTokenTeste(valida=False)
