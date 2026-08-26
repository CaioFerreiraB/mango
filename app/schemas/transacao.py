"""Schemas de `transacao` (Pluggy-owned): leitura + update estreito (flags/override §4.5)."""

from pydantic import BaseModel, Field, field_validator

from app.models.transacao import Transacao
from app.schemas.auto import read_model

TransacaoRead = read_model(Transacao)


class TransacaoUpdate(BaseModel):
    """Só os campos do usuário (§4 crud.md). `exclude_unset` no router → patch parcial."""

    eh_transferencia: bool | None = None
    revisada: bool | None = None
    # Categorias do Pluggy vão até 9 dígitos (ex.: 200300000) — 16 dá folga (igual ao model).
    categoria_override_id: str | None = Field(default=None, max_length=16)
    categoria_ajustada_usuario: bool | None = None
    # Vínculo com assinatura (§4.7): id (posse validada no router) ou None p/ desvincular.
    assinatura_id: int | None = None
    # "Não é assinatura": suprime detecção/sugestão para esta transação (§4.7).
    nao_e_assinatura: bool | None = None
    # Vínculo com um provento de investimento (§4.9): id do movimento (posse validada no router,
    # pelo investimento pai) ou None p/ desvincular.
    investimento_transacao_id: int | None = None
    # Texto do usuário (§4.5): descrição própria (substitui a do banco na listagem) e observação
    # livre. `None` limpa o campo.
    descricao_usuario: str | None = Field(default=None, max_length=255)
    observacoes: str | None = Field(default=None, max_length=2000)

    @field_validator("descricao_usuario", "observacoes")
    @classmethod
    def _vazio_vira_nulo(cls, v: str | None) -> str | None:
        """Campo apagado na UI chega como "" — guardar isso quebraria o fallback para o texto
        do banco (string vazia não é null)."""
        return v.strip() or None if v is not None else None


class TransacaoListagem(BaseModel):
    """Página server-side p/ a tabela (§5.3): itens + total para a paginação."""

    items: list[TransacaoRead]
    total: int
