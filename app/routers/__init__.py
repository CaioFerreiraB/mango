"""Monta `all_routers` (incluído pelo `app.main`).

User-owned simples → factory de CRUD; Pluggy sem write → factory read-only; entidades com
regra/segredo/validação própria → routers manuais.
"""

from fastapi import APIRouter

from app.repositories.assinatura import AssinaturaRepository
from app.repositories.ativo import AtivoRepository
from app.repositories.divisao import DivisaoDespesaRepository
from app.repositories.fatura import FaturaRepository
from app.repositories.orcamento import OrcamentoMensalRepository
from app.repositories.pluggy import InstituicaoRepository
from app.repositories.telegram import ConfigTelegramRepository
from app.routers import (
    assinatura as assinatura_router,
)
from app.routers import (
    auth,
    categoria,
    conta,
    credencial,
    dashboard,
    fonte_de_renda,
    indicadores,
    investimento,
    item,
    objetivo,
    orcamento,
    perfil,
    pluggy,
    setup,
    sync,
    transacao,
)
from app.routers.factory import make_crud_router, make_readonly_router
from app.schemas import assinatura, divisao
from app.schemas import ativo as ativo_schemas
from app.schemas import orcamento as orcamento_schemas
from app.schemas import telegram as telegram_schemas
from app.schemas.cartao_fatura import FaturaRead
from app.schemas.pluggy import InstituicaoRead
from app.services.assinatura_match import revincular_assinatura


def _revincular_ao_editar_aliases(repo, obj, campos: dict) -> None:
    """Editar os aliases de uma assinatura re-vincula as transações que casam (§4.7)."""
    if "nomes_transacao" in campos:
        revincular_assinatura(repo.db, repo.usuario_id, obj)


# CRUD completo (entidades do usuário) — via factory.
_crud = [
    make_crud_router(
        prefix="/ativos",
        tag="ativo",
        repo_cls=AtivoRepository,
        create_schema=ativo_schemas.AtivoCreate,
        update_schema=ativo_schemas.AtivoUpdate,
        read_schema=ativo_schemas.AtivoRead,
        nome="ativo",
    ),
    make_crud_router(
        prefix="/assinaturas",
        tag="assinatura",
        repo_cls=AssinaturaRepository,
        create_schema=assinatura.AssinaturaCreate,
        update_schema=assinatura.AssinaturaUpdate,
        read_schema=assinatura.AssinaturaRead,
        nome="assinatura",
        after_update=_revincular_ao_editar_aliases,
    ),
    make_crud_router(
        prefix="/divisoes-despesa",
        tag="divisao_despesa",
        repo_cls=DivisaoDespesaRepository,
        create_schema=divisao.DivisaoDespesaCreate,
        update_schema=divisao.DivisaoDespesaUpdate,
        read_schema=divisao.DivisaoDespesaRead,
        nome="divisão",
    ),
    make_crud_router(
        prefix="/config-telegram",
        tag="config_telegram",
        repo_cls=ConfigTelegramRepository,
        create_schema=telegram_schemas.ConfigTelegramCreate,
        update_schema=telegram_schemas.ConfigTelegramUpdate,
        read_schema=telegram_schemas.ConfigTelegramRead,
        nome="config",
    ),
    make_crud_router(
        prefix="/orcamentos-mensais",
        tag="orcamento_mensal",
        repo_cls=OrcamentoMensalRepository,
        create_schema=orcamento_schemas.OrcamentoMensalCreate,
        update_schema=orcamento_schemas.OrcamentoMensalUpdate,
        read_schema=orcamento_schemas.OrcamentoMensalRead,
        nome="orçamento mensal",
    ),
]

# Somente leitura (entidades do Pluggy sem write do usuário) — via factory.
_readonly = [
    make_readonly_router(
        prefix="/instituicoes",
        tag="instituicao",
        repo_cls=InstituicaoRepository,
        read_schema=InstituicaoRead,
        nome="instituição",
    ),
    make_readonly_router(
        prefix="/faturas",
        tag="fatura",
        repo_cls=FaturaRepository,
        read_schema=FaturaRead,
        nome="fatura",
    ),
]

# Routers manuais (CRUD/segredo/regra/narrow próprios).
_manuais: list[APIRouter] = [
    setup.router,  # público (first-run)
    auth.router,  # público (login/recuperação) + /me
    perfil.router,  # cadastro do próprio usuário (§4.1)
    fonte_de_renda.router,
    conta.router,  # read + narrow (objetivo_id, instituição manual)
    credencial.router,
    pluggy.router,  # /pluggy/connectores (catálogo p/ vínculo manual)
    item.router,
    sync.router,  # POST /sync + /itens-pluggy/{id}/sincronizar (§4.3)
    dashboard.router,  # agregações (§4.10)
    orcamento.router,
    objetivo.router,  # CRUD + leitura enriquecida (valor guardado/progresso)
    transacao.router,
    investimento.router,
    indicadores.router,  # dados de mercado p/ comparação da carteira (§4.9)
    categoria.router,
]

# `assinatura_router` (só `/assinaturas/resumo`) vem ANTES do CRUD-factory de `/assinaturas`:
# como `/{item_id}` valida o segmento como int só depois de casar a rota, `resumo` cairia num
# 422 se o factory viesse primeiro. Ordem de inclusão = ordem de match (Starlette).
all_routers: list[APIRouter] = [assinatura_router.router, *_crud, *_readonly, *_manuais]
