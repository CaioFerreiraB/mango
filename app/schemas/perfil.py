"""Schemas do perfil do usuário (§4.1). Update com campos **explícitos** — nunca
mass-assignment de `senha_hash`/`totp_secret_cifrado`/`usuario_id` (S4)."""

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_serializer

from app.schemas import ORMModel
from app.schemas.setup import _normalizar_email

Accent = Literal["violeta", "tangerina", "lima", "azul", "rosa", "grafite"]


class WidgetLayout(BaseModel):
    """Um widget do dashboard (das três abas): id do catálogo do frontend, largura em colunas de
    um grid de 60 (frações ⅙ … inteira, onde a borda arrastada encaixa), altura mínima em px
    opcional (ausente = a do conteúdo) e visibilidade. Id desconhecido é aceito (o frontend
    ignora) — o catálogo mora no cliente."""

    id: str = Field(pattern=r"^[a-z][a-z-]{0,31}$")
    largura: Literal[10, 12, 15, 20, 24, 30, 36, 40, 45, 48, 50, 60]
    altura: int | None = Field(default=None, ge=96, le=1600)
    visivel: bool

    @model_serializer(mode="wrap")
    def _sem_altura_nula(self, handler):
        # Altura ausente não vira `"altura": null` gravado/devolvido: o layout volta como foi salvo.
        d = handler(self)
        if d.get("altura") is None:
            d.pop("altura", None)
        return d


def _ids_unicos(v: list[WidgetLayout] | None) -> list[WidgetLayout] | None:
    if v is not None and len({w.id for w in v}) != len(v):
        raise ValueError("widget repetido no layout")
    return v


IdAtalho = Annotated[str, Field(pattern=r"^[a-z][a-z-]{0,31}$")]


def _atalhos_unicos(v: list[str] | None) -> list[str] | None:
    if v is not None and len(set(v)) != len(v):
        raise ValueError("atalho repetido")
    return v


class PerfilRead(ORMModel):
    id: int
    nome: str
    email: str
    data_nascimento: date | None
    salario_mensal_centavos: int | None
    formacao: str | None
    ocupacao: str | None
    accent: Accent | None
    avatar: int | None
    orcamento_alerta_pct: int  # % do orçamento da categoria que dispara o aviso no Telegram
    # Corte da fila de revisão (§4.3): null = sem corte, todo o histórico pede revisão.
    revisao_desde: date | None
    # Booleano derivado (o token brapi nunca é devolvido — §5.5).
    brapi_token_configurado: bool
    # 2FA opcional (§5.2, #15): booleanos derivados, o segredo nunca é devolvido.
    totp_configurado: bool
    totp_login_habilitado: bool
    # Ordem/largura/visibilidade dos widgets do dashboard; null = layout padrão.
    dashboard_layout: list[WidgetLayout] | None
    # Atalhos da barra inferior do celular além do "Início" fixo; null = padrão do frontend.
    atalhos_mobile: list[str] | None


class PerfilUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=255)
    email: str | None = None
    data_nascimento: date | None = None
    salario_mensal_centavos: int | None = Field(default=None, ge=0)
    formacao: str | None = Field(default=None, max_length=255)
    ocupacao: str | None = Field(default=None, max_length=255)
    accent: Accent | None = None
    avatar: int | None = Field(default=None, ge=1, le=4)
    revisao_desde: date | None = None
    # `int` (não `int | None`): a coluna é NOT NULL, então `null` explícito vira 422 na fronteira
    # em vez de IntegrityError no commit. O default None só marca "não enviado" (exclude_unset).
    orcamento_alerta_pct: int = Field(default=None, ge=1, le=100)
    # `null` explícito restaura o padrão; teto de 30 itens barra payload inflado.
    dashboard_layout: list[WidgetLayout] | None = Field(default=None, max_length=60)

    # Até 3 atalhos (o "Início" é fixo); ids do catálogo do frontend, que ignora os desconhecidos.
    atalhos_mobile: list[IdAtalho] | None = Field(default=None, max_length=3)

    _layout_unico = field_validator("dashboard_layout")(_ids_unicos)
    _atalhos_unicos = field_validator("atalhos_mobile")(_atalhos_unicos)

    @field_validator("email")
    @classmethod
    def _valida_email(cls, v: str | None) -> str | None:
        return None if v is None else _normalizar_email(v)


class BrapiTokenSet(BaseModel):
    """Grava o token brapi (write-only, cifrado em repouso). Nunca é lido de volta."""

    token: str = Field(min_length=1, max_length=512)


class BrapiTokenTeste(BaseModel):
    valida: bool


# --- 2FA (§5.2, #15): cadastrar/trocar exige reconfirmar a senha atual (step-up) ---------------


class TotpIniciarRequest(BaseModel):
    senha_atual: str = Field(min_length=1)


class TotpIniciado(BaseModel):
    """Passo 1 de cadastrar/trocar o 2FA — mesmo shape do setup/convite, ticket cifrado."""

    totp_secret: str
    totp_provisioning_uri: str
    ticket: str


class TotpConfirmarRequest(BaseModel):
    ticket: str = Field(min_length=1)
    codigo_totp: str = Field(min_length=6, max_length=8)


class TotpDesabilitarRequest(BaseModel):
    senha_atual: str = Field(min_length=1)
