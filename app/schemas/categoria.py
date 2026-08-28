"""Schemas de `categoria` (§4.5): taxonomia do Pluggy + personalizadas do usuário.

`CategoriaRead` é declarado à mão, e não por `read_model(Categoria)`, por dois motivos: `usuario_id`
não deve aparecer na API (a listagem já só devolve linha global ou do próprio usuário — não expor o
id é o default correto), e `personalizada`/`ativa` são derivados, não colunas.
"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.enums import ICONE_CATEGORIA
from app.models.categoria import Categoria

NOME_MIN = 2
NOME_MAX = 60

# Allowlist na fronteira (S4): o ícone é escolha do usuário e vira nome de componente no cliente.
# `Literal` porque assim o nome válido também sai no OpenAPI — o seletor do frontend não precisa
# manter uma segunda lista à mão.
Icone = Literal[ICONE_CATEGORIA]  # type: ignore[valid-type]


class CategoriaRead(BaseModel):
    pluggy_id: str
    description: str
    description_translated: str | None = None
    parent_id: str | None = None
    # Só a personalizada tem: a do Pluggy deriva o ícone da raiz do `pluggy_id`.
    icone: Icone | None = None
    # Criada pelo usuário → pode ser renomeada e excluída (a do Pluggy, só ativada/desativada).
    personalizada: bool
    # Ausência de linha em `categoria_desativada` para este usuário.
    ativa: bool

    @classmethod
    def de_modelo(cls, obj: Categoria, *, desativadas: set[str]) -> "CategoriaRead":
        return cls(
            pluggy_id=obj.pluggy_id,
            description=obj.description,
            description_translated=obj.description_translated,
            parent_id=obj.parent_id,
            # Um nome que saiu do catálogo (downgrade do produto) vira None em vez de estourar a
            # listagem inteira — a categoria continua legível, só sem o ícone escolhido.
            icone=obj.icone if obj.icone in ICONE_CATEGORIA else None,
            personalizada=obj.usuario_id is not None,
            ativa=obj.pluggy_id not in desativadas,
        )


def _nome_limpo(v: str) -> str:
    limpo = " ".join(v.split())
    if len(limpo) < NOME_MIN:
        raise ValueError(f"o nome precisa de pelo menos {NOME_MIN} caracteres")
    return limpo


class CategoriaCreate(BaseModel):
    """Criação de categoria personalizada. Nome e ícone: a hierarquia do Pluggy é dele, e uma
    categoria do usuário nasce plana (nível raiz)."""

    nome: str = Field(min_length=NOME_MIN, max_length=NOME_MAX)
    icone: Icone | None = None

    @field_validator("nome")
    @classmethod
    def _limpar(cls, v: str) -> str:
        return _nome_limpo(v)


class CategoriaUpdate(BaseModel):
    """`nome` e `icone` só valem para personalizada; `ativa` vale para as duas (é estado por
    usuário)."""

    nome: str | None = Field(default=None, min_length=NOME_MIN, max_length=NOME_MAX)
    icone: Icone | None = None
    ativa: bool | None = None

    @field_validator("nome")
    @classmethod
    def _limpar(cls, v: str | None) -> str | None:
        return _nome_limpo(v) if v is not None else None
