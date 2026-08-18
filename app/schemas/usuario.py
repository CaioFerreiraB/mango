"""Schemas de busca/gestão de usuários da instância (§4.11 — "com quem" dividir/convidar, e a
gestão de usuários em Configurações, restrita ao administrador).

`UsuarioBusca` tem campos mínimos: nunca expõe e-mail/segredos de um usuário para o outro.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.divisao import StatusPessoa

# Eixo independente de `StatusPessoa` (que é derivado — já aceitou o convite ou não): `tipo`
# controla acesso completo ao app vs. só à divisão de contas. Definido na criação, mas alterável
# pelo administrador depois (`PATCH .../tipo`).
TipoUsuario = Literal["completo", "divisao"]


class MudarTipoRequest(BaseModel):
    tipo: TipoUsuario


class UsuarioBusca(BaseModel):
    id: int
    nome: str
    avatar: int | None
    status: StatusPessoa


class UsuarioAdminRead(BaseModel):
    id: int
    nome: str
    email: str
    tipo: TipoUsuario
    ativo: bool
    is_admin: bool
    status: StatusPessoa  # pendente (convite não aceito) vs já ativou a conta
    criado_em: datetime
