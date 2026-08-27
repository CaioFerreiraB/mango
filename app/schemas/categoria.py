"""Schemas de `categoria` (§4.5): taxonomia do Pluggy + personalizadas do usuário.

`CategoriaRead` é declarado à mão, e não por `read_model(Categoria)`, por dois motivos: `usuario_id`
não deve aparecer na API (a listagem já só devolve linha global ou do próprio usuário — não expor o
id é o default correto), e `personalizada`/`ativa` são derivados, não colunas.
"""

from pydantic import BaseModel, Field, field_validator

from app.models.categoria import Categoria

NOME_MIN = 2
NOME_MAX = 60


class CategoriaRead(BaseModel):
    pluggy_id: str
    description: str
    description_translated: str | None = None
    parent_id: str | None = None
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
            personalizada=obj.usuario_id is not None,
            ativa=obj.pluggy_id not in desativadas,
        )


def _nome_limpo(v: str) -> str:
    limpo = " ".join(v.split())
    if len(limpo) < NOME_MIN:
        raise ValueError(f"o nome precisa de pelo menos {NOME_MIN} caracteres")
    return limpo


class CategoriaCreate(BaseModel):
    """Criação de categoria personalizada. Só o nome: a hierarquia do Pluggy é dele, e uma
    categoria do usuário nasce plana (nível raiz)."""

    nome: str = Field(min_length=NOME_MIN, max_length=NOME_MAX)

    @field_validator("nome")
    @classmethod
    def _limpar(cls, v: str) -> str:
        return _nome_limpo(v)


class CategoriaUpdate(BaseModel):
    """`nome` só vale para personalizada; `ativa` vale para as duas (é estado por usuário)."""

    nome: str | None = Field(default=None, min_length=NOME_MIN, max_length=NOME_MAX)
    ativa: bool | None = None

    @field_validator("nome")
    @classmethod
    def _limpar(cls, v: str | None) -> str | None:
        return _nome_limpo(v) if v is not None else None
