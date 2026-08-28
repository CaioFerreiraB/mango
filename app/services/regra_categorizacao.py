"""Regras de negócio do CRUD de `regra_categorizacao` (§4.5).

Três validações que não são CRUD puro, e toda mutação reaplicando as regras — criar uma regra tem
de recategorizar o histórico na hora, senão ela só valeria para o que chegar no próximo sync.
"""

from sqlalchemy.orm import Session

from app.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.categoria import RegraCategorizacao
from app.repositories.categoria import CategoriaRepository
from app.repositories.regra_categorizacao import RegraCategorizacaoRepository
from app.services.categoria_regras import aplicar_regras_categorizacao
from app.services.texto import normalizar_texto

# Teto por usuário: o casamento "contém" custa O(transações × regras), então o limite é o que
# mantém esse produto previsível. Folgado para uso pessoal real (dezenas, não centenas).
MAX_REGRAS = 200


def listar(db: Session, usuario_id: int) -> list[RegraCategorizacao]:
    return RegraCategorizacaoRepository(db, usuario_id).list()


def obter(db: Session, usuario_id: int, regra_id: int) -> RegraCategorizacao:
    obj = RegraCategorizacaoRepository(db, usuario_id).get(regra_id)
    if obj is None:
        raise NotFoundError("regra não encontrada")
    return obj


def criar(
    db: Session, usuario_id: int, *, texto: str, tipo_match: str, categoria_id: str
) -> RegraCategorizacao:
    repo = RegraCategorizacaoRepository(db, usuario_id)
    if repo.contar() >= MAX_REGRAS:
        raise ValidationError(f"limite de {MAX_REGRAS} regras atingido — remova alguma antes")
    _validar_categoria(db, usuario_id, categoria_id)
    normalizado = normalizar_texto(texto)
    if repo.por_chave(normalizado, tipo_match) is not None:
        raise ConflictError(f"você já tem uma regra para “{texto}”")

    obj = repo.create(
        texto=texto,
        texto_normalizado=normalizado,
        tipo_match=tipo_match,
        categoria_id=categoria_id,
    )
    aplicar_regras_categorizacao(db, usuario_id)
    return obj


def atualizar(
    db: Session,
    usuario_id: int,
    regra_id: int,
    *,
    texto: str | None = None,
    tipo_match: str | None = None,
    categoria_id: str | None = None,
) -> RegraCategorizacao:
    repo = RegraCategorizacaoRepository(db, usuario_id)
    obj = repo.get(regra_id)
    if obj is None:
        raise NotFoundError("regra não encontrada")
    if categoria_id is not None:
        _validar_categoria(db, usuario_id, categoria_id)

    campos: dict[str, object] = {}
    if texto is not None:
        campos["texto"] = texto
        campos["texto_normalizado"] = normalizar_texto(texto)
    if tipo_match is not None:
        campos["tipo_match"] = tipo_match
    if categoria_id is not None:
        campos["categoria_id"] = categoria_id

    if campos:
        # A chave de unicidade é (texto_normalizado, tipo_match) — qualquer um dos dois mudando
        # pode colidir com outra regra.
        chave = (
            campos.get("texto_normalizado", obj.texto_normalizado),
            campos.get("tipo_match", obj.tipo_match),
        )
        colisao = repo.por_chave(*chave)
        if colisao is not None and colisao.id != obj.id:
            raise ConflictError(f"você já tem uma regra para “{campos.get('texto', obj.texto)}”")
        repo.update(obj, **campos)
        aplicar_regras_categorizacao(db, usuario_id)
    return obj


def remover(db: Session, usuario_id: int, regra_id: int) -> None:
    repo = RegraCategorizacaoRepository(db, usuario_id)
    obj = repo.get(regra_id)
    if obj is None:
        raise NotFoundError("regra não encontrada")
    repo.delete(obj)
    # Reaplicar é o que limpa `categoria_regra_id` das transações que esta regra dominava.
    aplicar_regras_categorizacao(db, usuario_id)


def _validar_categoria(db: Session, usuario_id: int, categoria_id: str) -> None:
    """A categoria precisa ser visível ao usuário (global ou dele) e estar ativa (S3).

    Sem a checagem de posse, uma regra poderia apontar para a categoria personalizada de outro
    usuário; sem a de ativação, o usuário criaria uma regra para algo que ele mesmo escondeu.
    """
    repo = CategoriaRepository(db, usuario_id)
    if repo.get(categoria_id) is None:
        raise ValidationError("categoria não encontrada")
    if categoria_id in repo.desativadas():
        raise ValidationError("esta categoria está desativada — reative-a antes de usá-la em regra")
