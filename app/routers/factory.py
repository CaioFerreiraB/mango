"""Fábricas de routers — removem a duplicação de CRUD entre as entidades user-owned.

Mantêm a regra "lógica de negócio fora das rotas" (§5.2): as rotas só orquestram
repositório + tradução HTTP. Entidades com regra própria (ex.: orçamento #20) têm router
manual que chama o service.
"""

from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.usuario import Usuario
from app.repositories.base import UserScopedRepository
from app.security.current_user import get_current_user


def make_crud_router(
    *,
    prefix: str,
    tag: str,
    repo_cls: type[UserScopedRepository],
    create_schema: type,
    update_schema: type,
    read_schema: type,
    nome: str = "recurso",
    after_update: Callable[[UserScopedRepository, object, dict], None] | None = None,
) -> APIRouter:
    """CRUD completo de uma entidade do usuário (isolada por `usuario_id`)."""
    router = APIRouter(prefix=prefix, tags=[tag])

    def _repo(
        db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)
    ) -> UserScopedRepository:
        return repo_cls(db, user.id)

    @router.get("", response_model=list[read_schema])
    def listar(repo: UserScopedRepository = Depends(_repo)):
        return repo.list()

    @router.post("", response_model=read_schema, status_code=status.HTTP_201_CREATED)
    def criar(payload: create_schema, repo: UserScopedRepository = Depends(_repo)):
        return repo.create(**payload.model_dump())

    @router.get("/{item_id}", response_model=read_schema)
    def obter(item_id: int, repo: UserScopedRepository = Depends(_repo)):
        obj = repo.get(item_id)
        if obj is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"{nome} não encontrado")
        return obj

    @router.patch("/{item_id}", response_model=read_schema)
    def atualizar(
        item_id: int, payload: update_schema, repo: UserScopedRepository = Depends(_repo)
    ):
        obj = repo.get(item_id)
        if obj is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"{nome} não encontrado")
        campos = payload.model_dump(exclude_unset=True)
        obj = repo.update(obj, **campos)
        if after_update is not None:
            after_update(repo, obj, campos)
        return obj

    @router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
    def remover(item_id: int, repo: UserScopedRepository = Depends(_repo)):
        obj = repo.get(item_id)
        if obj is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"{nome} não encontrado")
        repo.delete(obj)

    return router


def make_readonly_router(
    *,
    prefix: str,
    tag: str,
    repo_cls: type[UserScopedRepository],
    read_schema: type,
    nome: str = "recurso",
) -> APIRouter:
    """Somente leitura (list + get) — entidades do Pluggy sem write do usuário."""
    router = APIRouter(prefix=prefix, tags=[tag])

    def _repo(
        db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)
    ) -> UserScopedRepository:
        return repo_cls(db, user.id)

    @router.get("", response_model=list[read_schema])
    def listar(repo: UserScopedRepository = Depends(_repo)):
        return repo.list()

    @router.get("/{item_id}", response_model=read_schema)
    def obter(item_id: int, repo: UserScopedRepository = Depends(_repo)):
        obj = repo.get(item_id)
        if obj is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"{nome} não encontrado")
        return obj

    return router
