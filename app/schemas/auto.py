"""Gera schemas de LEITURA a partir dos models (DRY entre as ~24 entidades).

Só para Read (sem validação a impor). Create/Update continuam explícitos, com `Literal`
para enums e limites — Pydantic é a fonte de verdade da validação de entrada (§5.3).
Colunas sensíveis (`*_cifrado`) podem ser excluídas e nunca vão para a resposta (§5.5).
"""

from typing import Any

from pydantic import ConfigDict, create_model
from sqlalchemy import inspect as sa_inspect

from app.db.base import Base


def read_model(
    model: type[Base],
    *,
    name: str | None = None,
    exclude: tuple[str, ...] = (),
    overrides: dict[str, Any] | None = None,
):
    # `overrides`: tipo por coluna quando o inferido não serve — JSON, por ex., vira `dict` mas
    # pode guardar uma `list[str]`.
    overrides = overrides or {}
    campos: dict[str, Any] = {}
    for col in sa_inspect(model).columns:
        if col.key in exclude:
            continue
        py_type = overrides.get(col.key) or col.type.python_type
        if col.nullable:
            campos[col.key] = (py_type | None, None)
        else:
            campos[col.key] = (py_type, ...)
    return create_model(
        name or f"{model.__name__}Read",
        __config__=ConfigDict(from_attributes=True),
        **campos,
    )
