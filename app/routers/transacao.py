"""Router de `transacao` (Pluggy-owned): leitura filtrada/paginada + update estreito (§4.5).

Validação de fronteira (S4): `order` e `tipo` por allowlist (`Literal`), `limit` com teto,
`offset` não-negativo — tudo imposto pelo FastAPI/Pydantic.
"""

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.assinatura import Assinatura
from app.models.investimento import InvestimentoTransacao
from app.models.transacao import Transacao
from app.models.usuario import Usuario
from app.repositories.assinatura import AssinaturaRepository
from app.repositories.investimento import InvestimentoRepository
from app.repositories.transacao import TransacaoRepository
from app.schemas.investimento import InvestimentoTransacaoRead
from app.schemas.transacao import TransacaoListagem, TransacaoRead, TransacaoUpdate
from app.security.current_user import get_current_user
from app.services import investimento as carteira_service
from app.services.assinatura_deteccao import normalizar_nome
from app.services.periodo import limites_sp

router = APIRouter(prefix="/transacoes", tags=["transacao"])


def _repo(
    db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)
) -> TransacaoRepository:
    return TransacaoRepository(db, user.id)


@router.get("", response_model=TransacaoListagem)
def listar(
    repo: TransacaoRepository = Depends(_repo),
    inicio: date | None = Query(None),
    fim: date | None = Query(None),
    conta_id: int | None = Query(None),
    categoria_id: str | None = Query(None, max_length=16),
    fatura_id: int | None = Query(None),
    tipo: Literal["DEBIT", "CREDIT"] | None = Query(None),
    revisada: bool | None = Query(None),
    eh_transferencia: bool | None = Query(None),
    assinatura_id: int | None = Query(None),
    tem_assinatura: bool | None = Query(None),
    busca: str | None = Query(None, max_length=200),
    order: Literal["date", "amount_centavos"] = Query("date"),
    descendente: bool = Query(True),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> TransacaoListagem:
    # Cada limite de data é resolvido no fuso SP (§4.10), independente do outro.
    ini = limites_sp(inicio, inicio)[0] if inicio else None
    fim_dt = limites_sp(fim, fim)[1] if fim else None
    itens, total = repo.listar_filtrado(
        inicio=ini,
        fim=fim_dt,
        conta_id=conta_id,
        categoria_id=categoria_id,
        fatura_id=fatura_id,
        tipo=tipo,
        revisada=revisada,
        eh_transferencia=eh_transferencia,
        assinatura_id=assinatura_id,
        tem_assinatura=tem_assinatura,
        busca=busca,
        order=order,
        descendente=descendente,
        limit=limit,
        offset=offset,
    )
    return TransacaoListagem(items=itens, total=total)


@router.get("/{transacao_id}", response_model=TransacaoRead)
def obter(transacao_id: int, repo: TransacaoRepository = Depends(_repo)):
    obj = repo.get(transacao_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "transação não encontrada")
    return obj


@router.get("/{transacao_id}/proventos-sugeridos", response_model=list[InvestimentoTransacaoRead])
def proventos_sugeridos(
    transacao_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Proventos candidatos a serem o crédito desta transação (mesmo valor, data ±5 dias)."""
    return carteira_service.proventos_sugeridos(db, user.id, transacao_id)


@router.patch("/{transacao_id}", response_model=TransacaoRead)
def atualizar(
    transacao_id: int, payload: TransacaoUpdate, repo: TransacaoRepository = Depends(_repo)
):
    obj = repo.get(transacao_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "transação não encontrada")
    dados = payload.model_dump(exclude_unset=True)
    # Mexer no flag de transferência é decisão explícita do usuário → vira "manual" e o
    # pareamento automático do próximo sync não a sobrescreve (§4.4).
    if "eh_transferencia" in dados:
        dados["transferencia_origem"] = "manual"
    # Vincular a assinatura: valida posse (S3) e aprende o nome da transação como alias, para o
    # sync casar cobranças futuras iguais (§4.7). `assinatura_id=None` desvincula.
    if dados.get("assinatura_id") is not None:
        assinatura = AssinaturaRepository(repo.db, repo.usuario_id).get(dados["assinatura_id"])
        if assinatura is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "assinatura não encontrada")
        _aprender_alias(repo.db, assinatura, obj)
    # Vincular a um provento de investimento (§4.9): valida posse PELO PAI (o movimento não tem
    # usuario_id). None desvincula.
    if dados.get("investimento_transacao_id") is not None:
        mov = repo.db.get(InvestimentoTransacao, dados["investimento_transacao_id"])
        if (
            mov is None
            or InvestimentoRepository(repo.db, repo.usuario_id).get(mov.investimento_id) is None
        ):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "provento não encontrado")
    return repo.update(obj, **dados)


def _aprender_alias(db: Session, assinatura: Assinatura, transacao: Transacao) -> None:
    """Adiciona o nome da transação aos `nomes_transacao` da assinatura, se ainda não estiver lá."""
    nome = (transacao.merchant_nome or transacao.description or "").strip()
    existentes = {normalizar_nome(n) for n in assinatura.nomes_transacao}
    if not nome or normalizar_nome(nome) in existentes:
        return
    assinatura.nomes_transacao = [*assinatura.nomes_transacao, nome]  # reatribui → ORM detecta
    db.commit()
