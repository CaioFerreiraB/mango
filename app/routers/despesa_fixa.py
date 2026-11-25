"""Router de despesas fixas (docs/dev/despesas-fixas.md).

Manual (não o factory): a listagem é enriquecida e materializa vencimentos na leitura, e as rotas
fixas (`/resumo`, `/ocorrencias/...`) são declaradas antes de `/{despesa_id}`.
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.despesa_fixa import DespesaFixa, DespesaFixaOcorrencia
from app.models.usuario import Usuario
from app.repositories.despesa_fixa import DespesaFixaRepository, OcorrenciaRepository
from app.schemas.despesa_fixa import (
    DespesaFixaCreate,
    DespesaFixaRead,
    DespesaFixaResumo,
    DespesaFixaUpdate,
    OcorrenciaRead,
    OcorrenciaUpdate,
)
from app.security.current_user import get_current_user
from app.services import despesa_fixa as service
from app.services.periodo import hoje_sp

router = APIRouter(prefix="/despesas-fixas", tags=["despesa_fixa"])


def _repo(
    db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)
) -> DespesaFixaRepository:
    return DespesaFixaRepository(db, user.id)


def _obter(repo: DespesaFixaRepository, despesa_id: int) -> DespesaFixa:
    obj = repo.get(despesa_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "despesa fixa não encontrada")
    return obj


def _ler(despesa: DespesaFixa, ocorrencias: list[DespesaFixaOcorrencia], hoje: date):
    return DespesaFixaRead.model_validate(despesa).model_copy(
        update=service.indicadores(despesa, ocorrencias, hoje)
    )


def _ler_um(repo: DespesaFixaRepository, despesa: DespesaFixa, hoje: date) -> DespesaFixaRead:
    service.materializar(repo.db, repo.usuario_id, hoje)
    repo.db.refresh(despesa)
    ocorrencias = service.ocorrencias_por_despesa(repo.db, repo.usuario_id).get(despesa.id, [])
    return _ler(despesa, ocorrencias, hoje)


@router.get("", response_model=list[DespesaFixaRead])
def listar(repo: DespesaFixaRepository = Depends(_repo)):
    hoje = hoje_sp()
    service.materializar(repo.db, repo.usuario_id, hoje)
    por = service.ocorrencias_por_despesa(repo.db, repo.usuario_id)
    despesas = repo.db.scalars(
        select(DespesaFixa)
        .where(DespesaFixa.usuario_id == repo.usuario_id)
        .order_by(DespesaFixa.ativa.desc(), DespesaFixa.dia_vencimento, DespesaFixa.id)
    ).all()
    return [_ler(d, por.get(d.id, []), hoje) for d in despesas]


@router.get("/resumo", response_model=DespesaFixaResumo)
def resumo(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    return service.resumo(db, user.id, hoje_sp())


@router.patch("/ocorrencias/{ocorrencia_id}", response_model=OcorrenciaRead)
def atualizar_ocorrencia(
    ocorrencia_id: int,
    payload: OcorrenciaUpdate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Pagar à mão (sem transação), pular o mês ou reabrir um vencimento (RF07)."""
    repo = OcorrenciaRepository(db, user.id)
    oc = repo.get(ocorrencia_id)
    if oc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "vencimento não encontrado")
    hoje = hoje_sp()
    pago_em = (payload.pago_em or hoje) if payload.status == "paga" else None
    oc = repo.update(oc, status=payload.status, pago_em=pago_em)
    return _ler_ocorrencia(db, oc, hoje)


def _ler_ocorrencia(
    db: Session, oc: DespesaFixaOcorrencia, hoje: date, qtd: dict[int, int] | None = None
) -> OcorrenciaRead:
    qtd = qtd if qtd is not None else service.qtd_transacoes(db, [oc.id])
    return OcorrenciaRead(
        id=oc.id,
        despesa_fixa_id=oc.despesa_fixa_id,
        vencimento=oc.vencimento,
        valor_centavos=oc.valor_centavos,
        status=oc.status,
        situacao=service.situacao_ocorrencia(oc, hoje),
        pago_em=oc.pago_em,
        qtd_transacoes=qtd.get(oc.id, 0),
    )


@router.post("", response_model=DespesaFixaRead, status_code=status.HTTP_201_CREATED)
def criar(payload: DespesaFixaCreate, repo: DespesaFixaRepository = Depends(_repo)):
    hoje = hoje_sp()
    obj = repo.create(
        **payload.model_dump(), retomada_em=service.piso_na_criacao(payload.inicio, hoje)
    )
    return _ler_um(repo, obj, hoje)


@router.get("/{despesa_id}", response_model=DespesaFixaRead)
def obter(despesa_id: int, repo: DespesaFixaRepository = Depends(_repo)):
    return _ler_um(repo, _obter(repo, despesa_id), hoje_sp())


@router.get("/{despesa_id}/ocorrencias", response_model=list[OcorrenciaRead])
def ocorrencias(despesa_id: int, repo: DespesaFixaRepository = Depends(_repo)):
    """Histórico de vencimentos, do mais recente para o mais antigo (RF15)."""
    despesa = _obter(repo, despesa_id)
    hoje = hoje_sp()
    service.materializar(repo.db, repo.usuario_id, hoje)
    lista = repo.db.scalars(
        select(DespesaFixaOcorrencia)
        .where(DespesaFixaOcorrencia.despesa_fixa_id == despesa.id)
        .order_by(DespesaFixaOcorrencia.vencimento.desc())
    ).all()
    qtd = service.qtd_transacoes(repo.db, [o.id for o in lista])
    return [_ler_ocorrencia(repo.db, o, hoje, qtd) for o in lista]


@router.patch("/{despesa_id}", response_model=DespesaFixaRead)
def atualizar(
    despesa_id: int, payload: DespesaFixaUpdate, repo: DespesaFixaRepository = Depends(_repo)
):
    obj = _obter(repo, despesa_id)
    campos = payload.model_dump(exclude_unset=True)
    inicio, fim = campos.get("inicio", obj.inicio), campos.get("fim", obj.fim)
    if fim is not None and fim < inicio:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "a data de término deve ser igual ou posterior à de início",
        )
    hoje = hoje_sp()
    reativando = campos.get("ativa") is True and not obj.ativa
    if reativando:
        campos["retomada_em"] = hoje  # o período inativo não vira atraso (RF09)
    mudou_agenda = any(
        campos.get(c, getattr(obj, c)) != getattr(obj, c) for c in service.CAMPOS_AGENDA
    )
    # Desativar também limpa os futuros em aberto: senão, reativada, a despesa herdaria como
    # atraso um vencimento que ainda nem tinha chegado quando ela foi pausada.
    if mudou_agenda or campos.get("ativa", obj.ativa) != obj.ativa:
        service.regenerar_futuras(repo.db, obj, hoje)
    obj = repo.update(obj, **campos)
    return _ler_um(repo, obj, hoje)


@router.delete("/{despesa_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover(despesa_id: int, repo: DespesaFixaRepository = Depends(_repo)):
    repo.delete(_obter(repo, despesa_id))
