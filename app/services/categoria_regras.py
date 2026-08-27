"""Regras de categorização: mapeia o nome de uma transação para uma categoria (§4.5).

Por que MATERIALIZAR em `transacao.categoria_regra_id` em vez de resolver na leitura: casar
"contém" contra a tabela de regras exigiria um join correlacionado com LIKE em toda agregação de
dashboard e orçamento. Aqui o custo é pago uma vez, quando o conjunto muda (sync ou CRUD de regra),
e o caminho de leitura continua sendo uma coluna indexada.

A coluna PERTENCE às regras: cada passada recalcula do zero o que está no escopo, então apagar uma
regra limpa sozinha as transações que ela dominava. `categoria_override_id` (ajuste manual) nunca
é tocado — a precedência é assinatura > manual > regra > Pluggy.

`casar` é PURA (não vê ORM nem sessão) para ser testável direto.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.categoria import RegraCategorizacao
from app.models.transacao import Transacao
from app.services.texto import normalizar_texto

# Lotes do `IN (...)` do UPDATE: o SQLite tem teto de variáveis por statement (999 nas builds
# antigas), então nunca mandamos a lista inteira de uma vez.
_TAMANHO_LOTE = 500


@dataclass(frozen=True)
class Regra:
    """Subconjunto de `regra_categorizacao` usado no casamento (desacopla do ORM p/ teste)."""

    id: int
    texto_normalizado: str
    tipo_match: str  # exato | contem
    categoria_id: str


@dataclass(frozen=True)
class RegrasCompiladas:
    """Índice pronto para casar: exatas em dict (O(1)); "contém" em lista já ordenada."""

    exatas: dict[str, str]
    contidas: tuple[tuple[str, str], ...]

    def __bool__(self) -> bool:
        return bool(self.exatas or self.contidas)


def compilar(regras: Iterable[Regra]) -> RegrasCompiladas:
    """Ordena os "contém" do mais específico para o menos: texto mais longo primeiro, empate
    resolvido pelo id (mais antiga vence). Sem isso o resultado dependeria da ordem do banco."""
    exatas: dict[str, str] = {}
    contidas: list[Regra] = []
    for r in regras:
        if not r.texto_normalizado:
            continue
        if r.tipo_match == "exato":
            # O UNIQUE (usuario_id, texto_normalizado, tipo_match) garante que não há colisão.
            exatas[r.texto_normalizado] = r.categoria_id
        else:
            contidas.append(r)
    contidas.sort(key=lambda r: (-len(r.texto_normalizado), r.id))
    return RegrasCompiladas(
        exatas=exatas,
        contidas=tuple((r.texto_normalizado, r.categoria_id) for r in contidas),
    )


def casar(nomes: Sequence[str | None], compiladas: RegrasCompiladas) -> str | None:
    """Categoria da primeira regra que casar, ou None.

    `nomes` são os candidatos da transação (`merchant_nome` e `description`) — casa se QUALQUER um
    bater. Exato vence "contém": uma regra escrita para o nome inteiro é mais específica do que uma
    escrita para um pedaço dele.
    """
    normalizados = [n for n in (normalizar_texto(x) for x in nomes) if n]
    if not normalizados:
        return None
    for n in normalizados:
        categoria_id = compiladas.exatas.get(n)
        if categoria_id is not None:
            return categoria_id
    for texto, categoria_id in compiladas.contidas:
        if any(texto in n for n in normalizados):
            return categoria_id
    return None


def regras_do_usuario(db: Session, usuario_id: int) -> list[Regra]:
    linhas = db.execute(
        select(
            RegraCategorizacao.id,
            RegraCategorizacao.texto_normalizado,
            RegraCategorizacao.tipo_match,
            RegraCategorizacao.categoria_id,
        ).where(RegraCategorizacao.usuario_id == usuario_id)
    ).all()
    return [Regra(*linha) for linha in linhas]


def aplicar_regras_categorizacao(db: Session, usuario_id: int, *, desde: date | None = None) -> int:
    """Recalcula `categoria_regra_id` das transações no escopo. Devolve quantas mudaram.

    `desde=None` (CRUD de regra) varre tudo do usuário — é o que faz uma regra apagada limpar as
    transações que ela dominava. Com `desde` (sync) varre só a janela: as antigas já estão certas,
    porque o conjunto de regras não mudou.
    """
    compiladas = compilar(regras_do_usuario(db, usuario_id))

    filtros = [Transacao.usuario_id == usuario_id]
    if desde is not None:
        filtros.append(Transacao.date >= datetime(desde.year, desde.month, desde.day))
    linhas = db.execute(
        select(
            Transacao.id,
            Transacao.merchant_nome,
            Transacao.description,
            Transacao.categoria_regra_id,
        ).where(*filtros)
    ).all()

    # Agrupa por categoria de destino → um UPDATE por categoria (em lotes), não um por transação.
    por_categoria: dict[str | None, list[int]] = {}
    for transacao_id, merchant_nome, descricao, atual in linhas:
        nova = casar((merchant_nome, descricao), compiladas)
        if nova != atual:
            por_categoria.setdefault(nova, []).append(transacao_id)

    total = 0
    for categoria_id, ids in por_categoria.items():
        for inicio in range(0, len(ids), _TAMANHO_LOTE):
            lote = ids[inicio : inicio + _TAMANHO_LOTE]
            db.execute(
                update(Transacao)
                .where(Transacao.usuario_id == usuario_id, Transacao.id.in_(lote))
                .values(categoria_regra_id=categoria_id)
                .execution_options(synchronize_session=False)
            )
            total += len(lote)
    if total:
        # Um único commit: `repo.update()` num laço daria um commit por transação (o padrão que
        # `assinatura_match.revincular_assinatura` usa e que não queremos repetir em escala).
        db.commit()
    return total
