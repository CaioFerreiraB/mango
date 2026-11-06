"""Router de orçamento — CRUD com a regra #20 (no service). `orcamento_mensal` é CRUD puro."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.usuario import Usuario
from app.repositories.orcamento import OrcamentoRepository
from app.routers.transacao import _read as ler_transacao
from app.schemas.orcamento import (
    OrcamentoConsumoRead,
    OrcamentoCreate,
    OrcamentoRead,
    OrcamentoUpdate,
)
from app.schemas.transacao import TransacaoListagem
from app.security.current_user import get_current_user
from app.services import orcamento as orcamento_service
from app.services import orcamento_consumo
from app.services.categoria_resolucao import carregar_contexto
from app.services.orcamento_mensal import materializar_mes

router = APIRouter(prefix="/orcamentos", tags=["orcamento"])


def _repo(
    db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)
) -> OrcamentoRepository:
    return OrcamentoRepository(db, user.id)


@router.get("", response_model=list[OrcamentoRead])
def listar(repo: OrcamentoRepository = Depends(_repo)):
    return repo.list()


@router.post("", response_model=OrcamentoRead, status_code=status.HTTP_201_CREATED)
def criar(
    payload: OrcamentoCreate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return orcamento_service.criar(db, user.id, payload.model_dump())


# Declarado antes de `/{orcamento_id}` para a rota estática não ser capturada pelo path param.
@router.get("/consumo", response_model=OrcamentoConsumoRead)
def consumo(
    ano: int = Query(ge=2000, le=2100),
    mes: int = Query(ge=1, le=12),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Consumo e alertas (50/75/90/100%) dos orçamentos do mês (§4.6)."""
    return orcamento_consumo.consumo_do_mes(db, user.id, ano, mes)


@router.get("/consumo/transacoes", response_model=TransacaoListagem)
def consumo_transacoes(
    ano: int = Query(ge=2000, le=2100),
    mes: int = Query(ge=1, le=12),
    tipo: Literal["despesa", "receita"] = Query(),
    categoria_id: str | None = Query(None, min_length=1, max_length=16),
    nao_planejado: bool = Query(False),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Transações que compõem uma linha do consumo do mês: a categoria (com subcategorias) ou,
    com `nao_planejado=true`, tudo do tipo que ficou fora do orçamento. Soma = realizado."""
    if (categoria_id is None) == (not nao_planejado):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "informe exatamente um entre categoria_id e nao_planejado=true",
        )
    itens = orcamento_consumo.transacoes_do_item(db, user.id, ano, mes, tipo, categoria_id)
    ctx = carregar_contexto(db, user.id)
    return TransacaoListagem(items=[ler_transacao(t, ctx) for t in itens], total=len(itens))


# Declarado antes de `/{orcamento_id}` pelo mesmo motivo de `/consumo`.
@router.post("/materializar", response_model=OrcamentoConsumoRead)
def materializar(
    ano: int = Query(ge=2000, le=2100),
    mes: int = Query(ge=1, le=12),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Aplica o orçamento padrão a um mês específico, sob pedido do usuário — normalmente pra
    um mês passado sem nada configurado (a materialização automática só cobre o mês corrente,
    §4.6). Idempotente: não sobrescreve linhas que já existem."""
    materializar_mes(db, user.id, ano, mes)
    return orcamento_consumo.consumo_do_mes(db, user.id, ano, mes)


@router.get("/{orcamento_id}", response_model=OrcamentoRead)
def obter(orcamento_id: int, repo: OrcamentoRepository = Depends(_repo)):
    orc = repo.get(orcamento_id)
    if orc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "orçamento não encontrado")
    return orc


@router.patch("/{orcamento_id}", response_model=OrcamentoRead)
def atualizar(
    orcamento_id: int,
    payload: OrcamentoUpdate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return orcamento_service.atualizar(
        db, user.id, orcamento_id, payload.model_dump(exclude_unset=True)
    )


@router.delete("/{orcamento_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover(orcamento_id: int, repo: OrcamentoRepository = Depends(_repo)):
    orc = repo.get(orcamento_id)
    if orc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "orçamento não encontrado")
    repo.delete(orc)
