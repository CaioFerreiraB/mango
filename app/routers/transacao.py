"""Router de `transacao` (Pluggy-owned): leitura filtrada/paginada + update estreito (§4.5).

Validação de fronteira (S4): `order` e `tipo` por allowlist (`Literal`), `limit` com teto,
`offset` não-negativo — tudo imposto pelo FastAPI/Pydantic.

A categoria devolvida (`categoria_efetiva_id`) sai de `categoria_resolucao`, a fonte única da
precedência assinatura > manual > regra > Pluggy (§4.5).
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
from app.repositories.categoria import CategoriaRepository
from app.repositories.investimento import InvestimentoRepository
from app.repositories.transacao import TransacaoRepository
from app.schemas.investimento import InvestimentoTransacaoRead
from app.schemas.transacao import TransacaoListagem, TransacaoRead, TransacaoUpdate
from app.security.current_user import get_current_user
from app.services import investimento as carteira_service
from app.services.assinatura_deteccao import normalizar_nome
from app.services.categoria_resolucao import Contexto, carregar_contexto, resolver
from app.services.compra_parcelada import irmas_da_compra
from app.services.periodo import janela_listagem
from app.services.revisao import corte_revisao

router = APIRouter(prefix="/transacoes", tags=["transacao"])


def _repo(
    db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)
) -> TransacaoRepository:
    return TransacaoRepository(db, user.id)


def _read(obj: Transacao, ctx: Contexto, *, parcelas: int = 0) -> TransacaoRead:
    categoria, origem = resolver(obj, ctx)
    return TransacaoRead.model_validate(obj).model_copy(
        update={
            "categoria_efetiva_id": categoria,
            "categoria_origem": origem,
            "parcelas_atualizadas": parcelas,
        }
    )


@router.get("", response_model=TransacaoListagem)
def listar(
    repo: TransacaoRepository = Depends(_repo),
    user: Usuario = Depends(get_current_user),
    inicio: date | None = Query(None),
    fim: date | None = Query(None),
    conta_id: int | None = Query(None),
    categoria_id: str | None = Query(None, max_length=16),
    fatura_id: int | None = Query(None),
    tipo: Literal["DEBIT", "CREDIT"] | None = Query(None),
    revisada: bool | None = Query(None),
    pendente_revisao: bool | None = Query(None),
    eh_transferencia: bool | None = Query(None),
    ocultar_pagamento_fatura: bool = Query(False),
    ocultar_futuras: bool = Query(False),
    assinatura_id: int | None = Query(None),
    tem_assinatura: bool | None = Query(None),
    busca: str | None = Query(None, max_length=200),
    order: Literal["date", "amount_centavos"] = Query("date"),
    descendente: bool = Query(True),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> TransacaoListagem:
    """Listagem paginada de transações. Todo filtro é opcional e combina por AND com os demais.

    Três pares pedem atenção porque parecem redundantes e não são: `revisada` é o filtro cru da
    coluna e `pendente_revisao` é o conceito de produto ("está na fila?", §4.3); `eh_transferencia`
    alcança toda transferência e `ocultar_pagamento_fatura` só o pagamento de fatura (§4.4), que é
    um subconjunto dela; `fim` é o limite escolhido pelo usuário e `ocultar_futuras` é o corte em
    hoje (§4.2) — juntos, prevalece o mais apertado.

    Os dois `ocultar_*` nascem DESLIGADOS aqui: quem decide o padrão de exibição é a tela, e o
    detalhe da fatura precisa da fatura inteira.
    """
    # Cada limite de data é resolvido no fuso SP (§4.10), independente do outro; `ocultar_futuras`
    # entra aqui porque é corte de data, não predicado — a regra mora em `periodo.janela_listagem`.
    ini, fim_dt = janela_listagem(inicio, fim, ocultar_futuras=ocultar_futuras)
    itens, total = repo.listar_filtrado(
        inicio=ini,
        fim=fim_dt,
        conta_id=conta_id,
        categoria_id=categoria_id,
        fatura_id=fatura_id,
        tipo=tipo,
        revisada=revisada,
        pendente_revisao=pendente_revisao,
        corte_revisao=corte_revisao(user.revisao_desde),
        eh_transferencia=eh_transferencia,
        ocultar_pagamento_fatura=ocultar_pagamento_fatura,
        assinatura_id=assinatura_id,
        tem_assinatura=tem_assinatura,
        busca=busca,
        order=order,
        descendente=descendente,
        limit=limit,
        offset=offset,
    )
    # Contexto carregado UMA vez por página (duas consultas pequenas), não por linha.
    ctx = carregar_contexto(repo.db, repo.usuario_id)
    return TransacaoListagem(items=[_read(t, ctx) for t in itens], total=total)


@router.get("/{transacao_id}", response_model=TransacaoRead)
def obter(transacao_id: int, repo: TransacaoRepository = Depends(_repo)):
    obj = repo.get(transacao_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "transação não encontrada")
    return _read(obj, carregar_contexto(repo.db, repo.usuario_id))


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
    # Validação inteira ANTES de qualquer escrita: `_aprender_alias` comita, e um PATCH recusado
    # depois disso deixaria a assinatura com um alias novo — que muda o pareamento automático dos
    # próximos syncs. Por isso a assinatura é só resolvida aqui e o alias só é aprendido no fim.
    assinatura = _assinatura_do_vinculo(repo, dados)
    _validar_provento(repo, dados)
    _validar_categoria_override(repo, dados)
    _recusar_categoria_de_assinatura(obj, dados)

    atualizada = repo.update(obj, **dados)
    if assinatura is not None:
        _aprender_alias(repo.db, assinatura, atualizada)
    parcelas = _propagar_para_parcelas(repo, atualizada) if "categoria_override_id" in dados else 0
    return _read(atualizada, carregar_contexto(repo.db, repo.usuario_id), parcelas=parcelas)


def _assinatura_do_vinculo(repo: TransacaoRepository, dados: dict) -> Assinatura | None:
    """A assinatura que o PATCH quer vincular, com posse validada (S3). Só LÊ: o alias que ela vai
    aprender (§4.7) é escrita, e escrever antes das demais validações deixaria rastro de um PATCH
    recusado. `assinatura_id=None` desvincula e não tem alias a aprender."""
    if dados.get("assinatura_id") is None:
        return None
    assinatura = AssinaturaRepository(repo.db, repo.usuario_id).get(dados["assinatura_id"])
    if assinatura is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "assinatura não encontrada")
    return assinatura


def _validar_provento(repo: TransacaoRepository, dados: dict) -> None:
    """Vínculo com provento de investimento (§4.9): posse validada PELO PAI (o movimento não tem
    `usuario_id`). None desvincula."""
    if dados.get("investimento_transacao_id") is None:
        return
    mov = repo.db.get(InvestimentoTransacao, dados["investimento_transacao_id"])
    if mov is None or InvestimentoRepository(repo.db, repo.usuario_id).get(mov.investimento_id) is (
        None
    ):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "provento não encontrado")


def _validar_categoria_override(repo: TransacaoRepository, dados: dict) -> None:
    """A categoria escolhida tem de ser visível ao usuário: global do Pluggy ou criada por ele (S3).

    A FK só exige que a linha exista, e `categoria` é a única tabela que mistura linha global com
    linha de usuário — sem esta checagem o PATCH aceitava o id da categoria PERSONALIZADA de outra
    conta. `CategoriaRepository` é o único ponto que sabe distinguir as duas coisas.

    Não exige que esteja ativa, ao contrário de `regra_categorizacao`: o seletor mantém na lista a
    categoria já escolhida mesmo inativa, e recusar o reenvio dela seria regressão. Criar uma regra
    nova é outra história — lá a exigência faz sentido e continua valendo.
    """
    if dados.get("categoria_override_id") is None:
        return
    if CategoriaRepository(repo.db, repo.usuario_id).get(dados["categoria_override_id"]) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "categoria não encontrada")


def _recusar_categoria_de_assinatura(obj: Transacao, dados: dict) -> None:
    """Cobrança de assinatura tem a categoria DA ASSINATURA (§4.5): duas cobranças da mesma
    assinatura em categorias diferentes é incoerência, não flexibilidade. Considera também o
    vínculo criado neste mesmo PATCH."""
    if "categoria_override_id" not in dados:
        return
    assinatura_id = dados["assinatura_id"] if "assinatura_id" in dados else obj.assinatura_id
    if assinatura_id is not None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "a categoria de uma cobrança de assinatura vem da assinatura — altere-a lá",
        )


def _propagar_para_parcelas(repo: TransacaoRepository, obj: Transacao) -> int:
    """Todas as parcelas de uma compra dividem a mesma categoria (§4.5) — trocar numa troca em
    todas. Pula as vinculadas a assinatura (a precedência mandaria nelas de qualquer forma)."""
    irmas = [t for t in irmas_da_compra(repo.db, repo.usuario_id, obj) if t.assinatura_id is None]
    for irma in irmas:
        irma.categoria_override_id = obj.categoria_override_id
        irma.categoria_ajustada_usuario = True
    if irmas:
        repo.db.commit()  # um commit para o grupo inteiro, não um por parcela
    return len(irmas)


def _aprender_alias(db: Session, assinatura: Assinatura, transacao: Transacao) -> None:
    """Adiciona o nome da transação aos `nomes_transacao` da assinatura, se ainda não estiver lá."""
    nome = (transacao.merchant_nome or transacao.description or "").strip()
    existentes = {normalizar_nome(n) for n in assinatura.nomes_transacao}
    if not nome or normalizar_nome(nome) in existentes:
        return
    assinatura.nomes_transacao = [*assinatura.nomes_transacao, nome]  # reatribui → ORM detecta
    db.commit()
