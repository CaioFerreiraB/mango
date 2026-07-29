"""Schemas das conexões Pluggy. Segredos entram em claro no payload e SAEM cifrados;
nunca são devolvidos pela API (§5.5) — por isso os Read excluem as colunas `*_cifrado`.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.pluggy import CredencialPluggy, Instituicao, ItemPluggy
from app.schemas.auto import read_model

InstituicaoRead = read_model(Instituicao)
# Read sem os segredos cifrados.
CredencialPluggyRead = read_model(
    CredencialPluggy, exclude=("client_id_cifrado", "client_secret_cifrado")
)
ItemPluggyRead = read_model(ItemPluggy, exclude=("pluggy_item_id",))


class CredencialTesteRead(BaseModel):
    """Resultado do teste ao vivo — só o booleano (nunca ecoa o segredo, S1)."""

    valida: bool


class ConnectorRead(BaseModel):
    """Item do catálogo do Pluggy (`GET /connectors`) para o seletor de instituição."""

    pluggy_connector_id: int
    nome: str
    logo_url: str | None = None


class CredencialPluggyCreate(BaseModel):
    client_id: str = Field(min_length=1)
    client_secret: str = Field(min_length=1)


class CredencialPluggyUpdate(BaseModel):
    client_id: str | None = Field(default=None, min_length=1)
    client_secret: str | None = Field(default=None, min_length=1)


class ItemPluggyCreate(BaseModel):
    credencial_id: int
    pluggy_item_id: str = Field(min_length=1)
    connector_id: int | None = None
    connector_nome: str | None = None
    status: str | None = None


class ItemPluggyUpdate(BaseModel):
    connector_nome: str | None = None
    status: str | None = None
    status_detalhe: str | None = None
    ultimo_sync_em: datetime | None = None
