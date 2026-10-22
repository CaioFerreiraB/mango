"""Router do acesso MCP (docs/mcp.md): a aba "MCP" das configurações do usuário.

Só pela sessão do navegador: `/acesso-mcp` fica fora da allowlist do token
(`app.security.current_user._ROTAS_TOKEN`), então um agente não consegue ler, trocar nem religar o
próprio token.
"""

import secrets
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.exceptions import NotFoundError
from app.models.acesso_mcp import AcessoMcp
from app.models.usuario import Usuario
from app.schemas.acesso_mcp import AcessoMcpRead, AcessoMcpUpdate, TokenMcp
from app.security.current_user import get_current_user, hash_token

router = APIRouter(prefix="/acesso-mcp", tags=["acesso_mcp"])

_PREFIXO_MCP = "mango_"
_TAM_PREFIXO_VISIVEL = len(_PREFIXO_MCP) + 4


def _acesso(db: Session, user: Usuario) -> AcessoMcp | None:
    return db.scalars(select(AcessoMcp).where(AcessoMcp.usuario_id == user.id)).first()


def _novo_token(acesso: AcessoMcp) -> None:
    token = _PREFIXO_MCP + secrets.token_urlsafe(32)
    acesso.token_hash = hash_token(token)
    acesso.token_cifrado = token
    acesso.token_gerado_em = datetime.now(UTC)
    acesso.ultimo_uso_em = None


def _read(acesso: AcessoMcp | None) -> AcessoMcpRead:
    if acesso is None:
        return AcessoMcpRead(
            configurado=False,
            ativo=False,
            escopo="leitura",
            prefixo=None,
            token_gerado_em=None,
            ultimo_uso_em=None,
        )
    return AcessoMcpRead(
        configurado=True,
        ativo=acesso.ativo,
        escopo=acesso.escopo,
        prefixo=acesso.token_cifrado[:_TAM_PREFIXO_VISIVEL],
        token_gerado_em=acesso.token_gerado_em,
        ultimo_uso_em=acesso.ultimo_uso_em,
    )


@router.get("", response_model=AcessoMcpRead)
def obter(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    return _read(_acesso(db, user))


@router.patch("", response_model=AcessoMcpRead)
def atualizar(
    payload: AcessoMcpUpdate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Liga/desliga e troca a permissão. A primeira ativação gera o token; desligar o mantém
    (religar volta a aceitar o mesmo token — trocar é ação explícita, `/trocar-token`)."""
    acesso = _acesso(db, user)
    if acesso is None:
        acesso = AcessoMcp(usuario_id=user.id, ativo=False, escopo="leitura")
        _novo_token(acesso)
        db.add(acesso)
    for campo, valor in payload.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(acesso, campo, valor)
    db.commit()
    db.refresh(acesso)
    return _read(acesso)


@router.get("/token", response_model=TokenMcp)
def revelar_token(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    acesso = _acesso(db, user)
    if acesso is None:
        raise NotFoundError("acesso MCP ainda não configurado")
    return TokenMcp(token=acesso.token_cifrado)


@router.post("/trocar-token", response_model=TokenMcp)
def trocar_token(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    """Gera um token novo; o anterior deixa de valer na hora (o hash antigo some do banco)."""
    acesso = _acesso(db, user)
    if acesso is None:
        raise NotFoundError("acesso MCP ainda não configurado")
    _novo_token(acesso)
    db.commit()
    return TokenMcp(token=acesso.token_cifrado)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def remover(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)) -> None:
    acesso = _acesso(db, user)
    if acesso is not None:
        db.delete(acesso)
        db.commit()
