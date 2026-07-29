"""Router de `investimento` (Pluggy-owned): leitura + update estreito (objetivo_id) +
agregados server-side da carteira (§4.9): resumo, série p/ comparação, movimentos e
proventos/DY. Rotas fixas (`/resumo`, `/serie`) declaradas ANTES de `/{investimento_id}`
(ordem de inclusão = ordem de match)."""

from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.investimento import InvestimentoTransacao
from app.models.usuario import Usuario
from app.repositories.ativo import AtivoRepository
from app.repositories.investimento import InvestimentoRepository
from app.repositories.objetivo import ObjetivoRepository
from app.schemas.investimento import (
    AporteManualCreate,
    AporteManualUpdate,
    CarteiraResumo,
    CarteiraSerie,
    CotaSeriePonto,
    FundamentosFII,
    InvestimentoRead,
    InvestimentoTransacaoRead,
    InvestimentoUpdate,
    ProventosFII,
    VisaoGeralInvestimentos,
)
from app.security.current_user import get_current_user
from app.services import investimento as carteira_service

router = APIRouter(prefix="/investimentos", tags=["investimento"])

# Teto de janela das consultas por período (bound de loop/fonte externa, S5).
_MAX_JANELA_DIAS = 3700


def _repo(
    db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)
) -> InvestimentoRepository:
    return InvestimentoRepository(db, user.id)


def _validar_periodo(inicio: date, fim: date) -> None:
    if inicio > fim or (fim - inicio) > timedelta(days=_MAX_JANELA_DIAS):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "período inválido")


@router.get("", response_model=list[InvestimentoRead])
def listar(repo: InvestimentoRepository = Depends(_repo)):
    return repo.list()


@router.get("/resumo", response_model=CarteiraResumo)
def resumo(
    db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)
) -> CarteiraResumo:
    return carteira_service.resumo_carteira(db, user.id)


@router.get("/visao-geral", response_model=VisaoGeralInvestimentos)
def visao_geral(
    db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)
) -> VisaoGeralInvestimentos:
    return carteira_service.visao_geral(db, user.id)


@router.get("/serie", response_model=CarteiraSerie)
def serie(
    inicio: date,
    fim: date,
    recorte: Literal["todos", "renda_fixa", "renda_variavel"] = "todos",
    subtype: str | None = Query(default=None, max_length=32),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
) -> CarteiraSerie:
    _validar_periodo(inicio, fim)
    return carteira_service.serie_carteira(
        db, user.id, inicio, fim, recorte=recorte, subtype=subtype
    )


# --- posição (grupo de investimento_ids do drawer) ------------------------------------
# Rotas fixas `/posicao/*` antes de `/{investimento_id}`. `ids` vem do cliente → cada id é
# validado (posse) no serviço; id de outro usuário/inexistente vira 404 (barra IDOR, S3).


@router.get("/posicao/transacoes", response_model=list[InvestimentoTransacaoRead])
def transacoes_posicao(
    ids: list[int] = Query(min_length=1, max_length=200),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return carteira_service.movimentos_posicao(db, user.id, ids)


@router.get("/posicao/serie", response_model=CarteiraSerie)
def serie_posicao(
    inicio: date,
    fim: date,
    ids: list[int] = Query(min_length=1, max_length=200),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
) -> CarteiraSerie:
    _validar_periodo(inicio, fim)
    return carteira_service.serie_posicao(db, user.id, ids, inicio, fim)


@router.get("/posicao/proventos", response_model=ProventosFII)
def proventos_posicao(
    inicio: date,
    fim: date,
    ids: list[int] = Query(min_length=1, max_length=200),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
) -> ProventosFII:
    _validar_periodo(inicio, fim)
    return carteira_service.proventos_posicao(db, user.id, ids, inicio, fim)


@router.get("/posicao/fundamentos", response_model=FundamentosFII)
def fundamentos_posicao(
    ids: list[int] = Query(min_length=1, max_length=200),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
) -> FundamentosFII:
    return carteira_service.fundamentos_posicao(db, user.id, ids)


@router.get("/posicao/cota-serie", response_model=list[CotaSeriePonto])
def cota_serie_posicao(
    inicio: date,
    fim: date,
    ids: list[int] = Query(min_length=1, max_length=200),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
) -> list[CotaSeriePonto]:
    _validar_periodo(inicio, fim)
    return carteira_service.cota_serie_posicao(db, user.id, ids, inicio, fim)


@router.post(
    "/{investimento_id}/aportes",
    response_model=InvestimentoTransacaoRead,
    status_code=status.HTTP_201_CREATED,
)
def criar_aporte(
    investimento_id: int,
    payload: AporteManualCreate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Adiciona um aporte (compra) à mão a uma posição — entra no custo médio (§4.9)."""
    return carteira_service.criar_aporte_manual(
        db, user.id, investimento_id, payload.data, payload.quantidade, payload.valor_centavos
    )


# Rotas de aporte por id (edição/remoção) — só o próprio aporte manual; movimento do Pluggy → 404.
@router.patch("/aportes/{aporte_id}", response_model=InvestimentoTransacaoRead)
def editar_aporte(
    aporte_id: int,
    payload: AporteManualUpdate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return carteira_service.editar_aporte_manual(
        db, user.id, aporte_id, payload.model_dump(exclude_unset=True)
    )


@router.delete("/aportes/{aporte_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_aporte(
    aporte_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    carteira_service.excluir_aporte_manual(db, user.id, aporte_id)


@router.get("/{investimento_id}", response_model=InvestimentoRead)
def obter(investimento_id: int, repo: InvestimentoRepository = Depends(_repo)):
    obj = repo.get(investimento_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "investimento não encontrado")
    return obj


@router.get("/{investimento_id}/transacoes", response_model=list[InvestimentoTransacaoRead])
def listar_transacoes(
    investimento_id: int,
    db: Session = Depends(get_db),
    repo: InvestimentoRepository = Depends(_repo),
):
    inv = repo.get(investimento_id)  # 404 também p/ investimento de outro usuário (S3)
    if inv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "investimento não encontrado")
    return db.scalars(
        select(InvestimentoTransacao)
        .where(InvestimentoTransacao.investimento_id == inv.id)
        .order_by(InvestimentoTransacao.date.desc(), InvestimentoTransacao.id.desc())
    ).all()


@router.get("/{investimento_id}/proventos", response_model=ProventosFII)
def proventos(
    investimento_id: int,
    inicio: date,
    fim: date,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
) -> ProventosFII:
    _validar_periodo(inicio, fim)
    return carteira_service.proventos_fii(db, user.id, investimento_id, inicio, fim)


@router.patch("/{investimento_id}", response_model=InvestimentoRead)
def atualizar(
    investimento_id: int,
    payload: InvestimentoUpdate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Campos do usuário na posição: objetivo (#4), ativo/agrupamento (§4.9) e custo manual
    (valor investido quando o Pluggy não fornece). Patch parcial (`exclude_unset`) — mexer só
    num campo não zera os outros. Posse validada (S3)."""
    repo = InvestimentoRepository(db, user.id)
    inv = repo.get(investimento_id)
    if inv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "investimento não encontrado")
    dados = payload.model_dump(exclude_unset=True)
    if dados.get("objetivo_id") is not None:
        if ObjetivoRepository(db, user.id).get(dados["objetivo_id"]) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "objetivo não encontrado")
    if dados.get("ativo_id") is not None:
        if AtivoRepository(db, user.id).get(dados["ativo_id"]) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "ativo não encontrado")
    return repo.update(inv, **dados)
