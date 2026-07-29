"""Router de `credencial_pluggy` — segredos entram em claro e nunca são devolvidos (§5.5)."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.usuario import Usuario
from app.pluggy.client import PluggyClient, PluggyError
from app.repositories.pluggy import CredencialPluggyRepository
from app.schemas.pluggy import (
    CredencialPluggyCreate,
    CredencialPluggyRead,
    CredencialPluggyUpdate,
    CredencialTesteRead,
)
from app.security.current_user import get_current_user

router = APIRouter(prefix="/credenciais-pluggy", tags=["credencial_pluggy"])


def _repo(
    db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)
) -> CredencialPluggyRepository:
    return CredencialPluggyRepository(db, user.id)


@router.get("", response_model=list[CredencialPluggyRead])
def listar(repo: CredencialPluggyRepository = Depends(_repo)):
    return repo.list()


@router.post("/testar", response_model=CredencialTesteRead)
def testar(repo: CredencialPluggyRepository = Depends(_repo)) -> CredencialTesteRead:
    """Valida a credencial guardada contra o Pluggy (`POST /auth`). Só devolve o booleano."""
    creds = repo.list()
    if not creds:
        return CredencialTesteRead(valida=False)
    cred = creds[0]
    try:
        with PluggyClient(cred.client_id_cifrado, cred.client_secret_cifrado) as client:
            client.autenticar()
        return CredencialTesteRead(valida=True)
    except PluggyError:
        return CredencialTesteRead(valida=False)


@router.post("", response_model=CredencialPluggyRead, status_code=status.HTTP_201_CREATED)
def criar(payload: CredencialPluggyCreate, repo: CredencialPluggyRepository = Depends(_repo)):
    return repo.create(
        client_id_cifrado=payload.client_id,
        client_secret_cifrado=payload.client_secret,
    )


@router.get("/{credencial_id}", response_model=CredencialPluggyRead)
def obter(credencial_id: int, repo: CredencialPluggyRepository = Depends(_repo)):
    cred = repo.get(credencial_id)
    if cred is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "credencial não encontrada")
    return cred


@router.patch("/{credencial_id}", response_model=CredencialPluggyRead)
def atualizar(
    credencial_id: int,
    payload: CredencialPluggyUpdate,
    repo: CredencialPluggyRepository = Depends(_repo),
):
    cred = repo.get(credencial_id)
    if cred is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "credencial não encontrada")
    campos: dict = {}
    if payload.client_id is not None:
        campos["client_id_cifrado"] = payload.client_id
    if payload.client_secret is not None:
        campos["client_secret_cifrado"] = payload.client_secret
    return repo.update(cred, **campos)


@router.delete("/{credencial_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover(credencial_id: int, repo: CredencialPluggyRepository = Depends(_repo)):
    cred = repo.get(credencial_id)
    if cred is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "credencial não encontrada")
    repo.delete(cred)
