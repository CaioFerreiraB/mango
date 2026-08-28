"""Regras de categoria personalizada e de ativação por usuário (§4.5).

Fora das rotas (§5.2): o router só traduz HTTP. Aqui ficam as três regras que não são CRUD puro —
nome único sem caixa/acento, exclusão que não pode estourar FK, e ativação que alcança a subárvore.
"""

from sqlalchemy.orm import Session

from app.exceptions import ConflictError, NotFoundError, ValidationError
from app.repositories.categoria import CategoriaRepository
from app.schemas.categoria import CategoriaRead
from app.services.categoria_arvore import com_descendentes


def listar(db: Session, usuario_id: int, *, apenas_ativas: bool = False) -> list[CategoriaRead]:
    repo = CategoriaRepository(db, usuario_id)
    desativadas = repo.desativadas()
    itens = [CategoriaRead.de_modelo(c, desativadas=desativadas) for c in repo.list()]
    return [c for c in itens if c.ativa] if apenas_ativas else itens


def obter(db: Session, usuario_id: int, pluggy_id: str) -> CategoriaRead:
    repo = CategoriaRepository(db, usuario_id)
    obj = repo.get(pluggy_id)
    if obj is None:
        raise NotFoundError("categoria não encontrada")
    return CategoriaRead.de_modelo(obj, desativadas=repo.desativadas())


def criar(db: Session, usuario_id: int, nome: str, icone: str | None = None) -> CategoriaRead:
    repo = CategoriaRepository(db, usuario_id)
    if repo.nome_em_uso(nome):
        raise ConflictError(f"você já tem uma categoria chamada “{nome}”")
    obj = repo.criar_personalizada(nome, icone)
    return CategoriaRead.de_modelo(obj, desativadas=repo.desativadas())


def atualizar(
    db: Session,
    usuario_id: int,
    pluggy_id: str,
    *,
    nome: str | None = None,
    icone: str | None = None,
    ativa: bool | None = None,
) -> CategoriaRead:
    repo = CategoriaRepository(db, usuario_id)
    obj = repo.get(pluggy_id)
    if obj is None:
        raise NotFoundError("categoria não encontrada")

    if nome is not None:
        # Renomear é escrita na linha: só na própria. A do Pluggy é compartilhada entre usuários,
        # renomeá-la mudaria a taxonomia de todo mundo.
        if repo.get_personalizada(pluggy_id) is None:
            raise ValidationError("só é possível renomear uma categoria criada por você")
        if repo.nome_em_uso(nome, ignorando=pluggy_id):
            raise ConflictError(f"você já tem uma categoria chamada “{nome}”")
        obj = repo.renomear(obj, nome)

    if icone is not None:
        # Mesmo motivo do nome: é escrita na linha, e a do Pluggy é compartilhada — lá o ícone vem
        # da raiz do `pluggy_id` e é o mesmo para todo mundo.
        if repo.get_personalizada(pluggy_id) is None:
            raise ValidationError("só é possível mudar o ícone de uma categoria criada por você")
        obj = repo.definir_icone(obj, icone)

    if ativa is not None:
        # Alcança a subárvore: desativar "Alimentação" sem levar as filhas junto deixaria as
        # subcategorias órfãs aparecendo sozinhas nos seletores.
        repo.definir_ativa(com_descendentes(db, usuario_id, pluggy_id), ativa)

    return CategoriaRead.de_modelo(obj, desativadas=repo.desativadas())


def remover(db: Session, usuario_id: int, pluggy_id: str) -> None:
    repo = CategoriaRepository(db, usuario_id)
    obj = repo.get_personalizada(pluggy_id)
    if obj is None:
        # 404 também quando existe mas é do Pluggy/de outro usuário: não confirma a existência.
        raise NotFoundError("categoria não encontrada")
    # `orcamento`/`orcamento_mensal` são NOT NULL com ondelete=RESTRICT — sem esta checagem o
    # DELETE viraria IntegrityError (500). Transação, assinatura e divisão são SET NULL.
    em_uso = repo.contar_orcamentos(pluggy_id)
    if em_uso:
        raise ConflictError(
            f"esta categoria está em uso em {em_uso} orçamento(s) — remova-a de lá antes de excluir"
        )
    repo.remover(obj)
