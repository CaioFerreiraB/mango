"""Divisão de contas (§4.11): rateio, saldos entre pessoas e leitura enriquecida.

`DivisaoDespesaRead` não é um `read_model` puro — `participantes` e `meu_saldo_centavos` são
calculados aqui em runtime, mesmo padrão de `enriquecer_um`/`listar` em `app/services/objetivo.py`.
Nada de `HTTPException`: erros de domínio (`app/exceptions.py`), traduzidos a HTTP no `main`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, case, func, literal, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from app.db.atomic import commit
from app.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.categoria import Categoria
from app.models.convite import ConviteUsuario
from app.models.divisao import DivisaoDespesa, DivisaoParticipante
from app.models.transacao import Transacao
from app.models.usuario import Usuario
from app.repositories.divisao import DivisaoDespesaRepository, EscopoDivisao
from app.repositories.transacao import TransacaoRepository, _escape_like
from app.schemas.divisao import (
    DivisaoDespesaCreate,
    DivisaoDespesaRead,
    DivisaoDespesaUpdate,
    DivisaoParticipanteRead,
    DivisaoVinculo,
    PessoaDivisao,
    ResumoDivisoes,
)
from app.schemas.transacao import DivisaoDaTransacao, DivisaoLancamento
from app.services import configuracao as configuracao_service
from app.services import divisao_otimizacao
from app.services.gasto_usuario import VALOR_EFETIVO, categoria_da_divisao

# (usuario_id, valor_centavos, percentual_bp | None) — uma linha de `divisao_participante`.
Linha = tuple[int, int, int | None]
MODOS_COM_PARTES = ("porcentagem", "valor")
CEM_POR_CENTO_BP = 10_000


def _validar_participantes(
    db: Session, pago_por_usuario_id: int, modo: str, participantes_ids: list[int]
) -> list[int]:
    """Valida o payload e devolve os ids que efetivamente recebem uma linha de participante."""
    if modo == "integral":
        distintos = set(participantes_ids)
        if len(distintos) != 1:
            raise ValidationError("modo integral exige exatamente 1 participante (o devedor)")
        devedor_id = participantes_ids[0]
        if devedor_id == pago_por_usuario_id:
            raise ValidationError("quem pagou não pode ser o devedor no modo integral")
        ids_a_validar = {devedor_id, pago_por_usuario_id}
    else:
        # "igualmente" sempre inclui quem pagou — todos pagam partes iguais (§4.11).
        ids_a_validar = set(participantes_ids) | {pago_por_usuario_id}
    _exigir_usuarios(db, ids_a_validar)
    return [devedor_id] if modo == "integral" else sorted(ids_a_validar)


def _exigir_usuarios(db: Session, ids: set[int]) -> None:
    existentes = set(db.scalars(select(Usuario.id).where(Usuario.id.in_(ids))).all())
    faltando = ids - existentes
    if faltando:
        raise NotFoundError(f"usuário(s) inexistente(s): {sorted(faltando)}")


def _validar_categoria(db: Session, categoria_id: str | None) -> None:
    if categoria_id is not None and db.get(Categoria, categoria_id) is None:
        raise NotFoundError("categoria não encontrada")


def _proporcional(total: int, pesos: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Reparte `total` centavos na proporção dos pesos, somando exatamente o total: cada um leva
    o piso da sua fatia e os centavos que sobram vão para os maiores restos (empate: menor id)."""
    soma = sum(p for _, p in pesos)
    fatias = [(uid, total * p // soma, total * p % soma) for uid, p in pesos]
    sobra = total - sum(base for _, base, _ in fatias)
    extra = {uid for uid, _, _ in sorted(fatias, key=lambda f: (-f[2], f[0]))[:sobra]}
    return [(uid, base + (uid in extra)) for uid, base, _ in fatias]


def _linhas_por_partes(
    db: Session, pago_por_usuario_id: int, modo: str, total: int, partes: list[tuple[int, int]]
) -> list[Linha]:
    """Valida as fatias (`porcentagem`: somam 100%; `valor`: somam o total) e devolve as linhas.
    Fatia zero não vira linha; precisa sobrar alguém além de quem pagou."""
    ids = [uid for uid, _ in partes]
    if len(set(ids)) != len(ids):
        raise ValidationError("cada pessoa aparece uma vez só na divisão")
    partes = sorted((uid, v) for uid, v in partes if v > 0)
    if not any(uid != pago_por_usuario_id for uid, _ in partes):
        raise ValidationError("a divisão precisa de alguém além de quem pagou")
    soma = sum(v for _, v in partes)
    if modo == "porcentagem":
        if soma != CEM_POR_CENTO_BP:
            raise ValidationError(f"as porcentagens somam {soma / 100:g}%, e não 100%")
    elif soma != total:
        raise ValidationError("a soma dos valores tem de ser igual ao valor total")
    _exigir_usuarios(db, {uid for uid, _ in partes} | {pago_por_usuario_id})
    if modo == "valor":
        return [(uid, v, None) for uid, v in partes]
    bp = dict(partes)
    return [(uid, v, bp[uid]) for uid, v in _proporcional(total, partes)]


def _rateio(valor_total_centavos: int, modo: str, participantes_ids: list[int]) -> list[Linha]:
    """Linhas de `igualmente`/`integral` — resto da divisão vai para os primeiros ids (decisão)."""
    if modo == "integral":
        return [(participantes_ids[0], valor_total_centavos, None)]
    ids = sorted(participantes_ids)
    base, resto = divmod(valor_total_centavos, len(ids))
    return [(uid, base + 1 if i < resto else base, None) for i, uid in enumerate(ids)]


def _linhas(
    db: Session,
    pago_por_usuario_id: int,
    modo: str,
    total: int,
    participantes: list[int],
    partes: list[tuple[int, int]] | None,
) -> list[Linha]:
    if modo in MODOS_COM_PARTES:
        if not partes:
            raise ValidationError("informe a parte de cada pessoa")
        return _linhas_por_partes(db, pago_por_usuario_id, modo, total, partes)
    if not participantes:
        raise ValidationError("informe com quem dividir")
    ids = _validar_participantes(db, pago_por_usuario_id, modo, participantes)
    return _rateio(total, modo, ids)


def _reajustar(linhas: list[Linha], modo: str, total: int) -> list[Linha]:
    """Mesmas pessoas, novo total: igualmente divide de novo; porcentagem segue as porcentagens;
    integral e valor escalam na proporção das partes atuais."""
    if modo == "igualmente":
        return _rateio(total, modo, [uid for uid, _, _ in linhas])
    pesos = [(uid, bp if modo == "porcentagem" else v) for uid, v, bp in sorted(linhas)]
    bps = {uid: bp for uid, _, bp in linhas}
    return [(uid, v, bps[uid]) for uid, v in _proporcional(total, pesos)]


def _total_reajustado(tx: Transacao) -> int:
    """Total de uma divisão reajustada à transação — precisa ser positivo (como na criação), senão
    as partes zeram e o próximo reajuste não teria proporção a seguir."""
    total = _valor_da_transacao(tx)
    if total <= 0:
        raise ValidationError("não dá para reajustar a divisão a uma transação de valor zero")
    return total


def _valor_da_transacao(tx: Transacao) -> int:
    return abs(
        tx.amount_in_account_currency_centavos
        if tx.amount_in_account_currency_centavos is not None
        else tx.amount_centavos
    )


def enriquecer(db: Session, usuario_id: int, despesa: DivisaoDespesa) -> DivisaoDespesaRead:
    linhas = list(
        db.scalars(
            select(DivisaoParticipante).where(DivisaoParticipante.divisao_id == despesa.id)
        ).all()
    )
    usuarios = {
        u.id: u
        for u in db.scalars(
            select(Usuario).where(Usuario.id.in_({linha.usuario_id for linha in linhas}))
        ).all()
    }
    participantes = [
        DivisaoParticipanteRead(
            usuario_id=linha.usuario_id,
            nome=usuarios[linha.usuario_id].nome,
            avatar=usuarios[linha.usuario_id].avatar,
            valor_centavos=linha.valor_centavos,
            percentual_bp=linha.percentual_bp,
        )
        for linha in linhas
        if linha.usuario_id in usuarios
    ]

    meu_saldo = 0
    if not despesa.quitada:
        if despesa.pago_por_usuario_id == usuario_id:
            meu_saldo = sum(
                linha.valor_centavos for linha in linhas if linha.usuario_id != usuario_id
            )
        else:
            minha_linha = next((linha for linha in linhas if linha.usuario_id == usuario_id), None)
            if minha_linha is not None:
                meu_saldo = -minha_linha.valor_centavos

    leitura = DivisaoDespesaRead.model_validate(despesa)
    leitura.participantes = participantes
    leitura.meu_saldo_centavos = meu_saldo
    return leitura


def listar(
    db: Session, usuario_id: int, escopo: EscopoDivisao = "todas"
) -> list[DivisaoDespesaRead]:
    repo = DivisaoDespesaRepository(db, usuario_id)
    return [enriquecer(db, usuario_id, d) for d in repo.listar(escopo)]


def obter(db: Session, usuario_id: int, despesa_id: int) -> DivisaoDespesaRead | None:
    repo = DivisaoDespesaRepository(db, usuario_id)
    despesa = repo.obter(despesa_id)
    return None if despesa is None else enriquecer(db, usuario_id, despesa)


def _transacao_vinculavel(db: Session, usuario_id: int, transacao_id: int) -> Transacao:
    """Transação do próprio usuário que pode representar uma despesa dividida (RF01)."""
    tx = TransacaoRepository(db, usuario_id).get(transacao_id)
    if tx is None:
        raise NotFoundError("transação não encontrada")
    if tx.type != "DEBIT" or tx.eh_transferencia:
        raise ValidationError("só uma saída que não seja transferência pode ser dividida")
    return tx


_JA_VINCULADA = "essa transação já está vinculada a outra divisão"


def _commit_vinculo(db: Session) -> None:
    """`transacao_id` é único: corrida entre dois vínculos da mesma transação vira 409."""
    try:
        commit(db)
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(_JA_VINCULADA) from exc


def criar(db: Session, usuario_id: int, payload: DivisaoDespesaCreate) -> DivisaoDespesaRead:
    linhas = _linhas(
        db,
        payload.pago_por_usuario_id,
        payload.modo_divisao,
        payload.valor_total_centavos,
        payload.participantes,
        [(p.usuario_id, p.valor) for p in payload.partes] if payload.partes else None,
    )
    _validar_categoria(db, payload.categoria_id)
    data = payload.data or datetime.now(UTC)
    total = payload.valor_total_centavos
    if payload.transacao_id is not None or payload.sem_transacao:
        if payload.pago_por_usuario_id != usuario_id:
            raise ValidationError("só quem pagou indica a transação")
        if payload.transacao_id is not None and payload.sem_transacao:
            raise ValidationError("informe a transação ou 'sem transação', não os dois")
    if payload.transacao_id is not None:
        tx = _transacao_vinculavel(db, usuario_id, payload.transacao_id)
        data = tx.date
        if payload.reajustar and _valor_da_transacao(tx) != total:
            total = _total_reajustado(tx)
            linhas = _reajustar(linhas, payload.modo_divisao, total)
    repo = DivisaoDespesaRepository(db, usuario_id)
    # Os `flush` de `criar`/`definir_participantes` já esbarram no UNIQUE de `transacao_id`:
    # o 409 cobre o bloco inteiro, não só o commit (divisão e participantes ficam atômicos).
    try:
        despesa = repo.criar(
            pago_por_usuario_id=payload.pago_por_usuario_id,
            descricao=payload.descricao,
            categoria_id=payload.categoria_id,
            valor_total_centavos=total,
            modo_divisao=payload.modo_divisao,
            quitada=False,
            arquivada=False,
            data=data,
            transacao_id=payload.transacao_id,
            sem_transacao=payload.sem_transacao,
        )
        repo.definir_participantes(despesa.id, linhas)
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(_JA_VINCULADA) from exc
    _commit_vinculo(db)
    db.refresh(despesa)
    return enriquecer(db, usuario_id, despesa)


def definir_vinculo(
    db: Session, usuario_id: int, despesa_id: int, payload: DivisaoVinculo
) -> DivisaoDespesaRead:
    """Só o pagador (RF02) — a transação vinculada é dele, mesmo que outra pessoa tenha criado."""
    despesa = DivisaoDespesaRepository(db, usuario_id).obter(despesa_id)
    if despesa is None:
        raise NotFoundError("despesa não encontrada")
    if despesa.pago_por_usuario_id != usuario_id:
        raise ValidationError("só quem pagou vincula a transação")
    if payload.transacao_id is not None and payload.sem_transacao:
        raise ValidationError("informe a transação ou 'sem transação', não os dois")
    lido = despesa.transacao_id
    valores = {"transacao_id": payload.transacao_id, "sem_transacao": payload.sem_transacao}
    reajustadas = None
    if payload.transacao_id is not None and payload.transacao_id != lido:
        if lido is not None:
            raise ConflictError("a divisão já tem transação; desvincule antes")
        tx = _transacao_vinculavel(db, usuario_id, payload.transacao_id)
        valores["data"] = tx.date
        novo_total = _valor_da_transacao(tx)
        if payload.reajustar and novo_total != despesa.valor_total_centavos:
            novo_total = _total_reajustado(tx)
            # Reajustar muda quanto os outros devem: decisão de quem criou a divisão (como editar).
            if despesa.criado_por_usuario_id != usuario_id:
                raise ValidationError("só quem criou a divisão pode reajustá-la")
            repo = DivisaoDespesaRepository(db, usuario_id)
            atuais = [
                (p.usuario_id, p.valor_centavos, p.percentual_bp)
                for p in repo.participantes(despesa.id)
            ]
            reajustadas = _reajustar(atuais, despesa.modo_divisao, novo_total)
            valores["valor_total_centavos"] = novo_total
    # Compare-and-set: só grava se o vínculo ainda é o que foi lido. Duas trocas concorrentes
    # leem o mesmo estado; a segunda não casa o WHERE e vira 409 em vez de sobrescrever a
    # primeira — vale no SQLite, onde `FOR UPDATE` não trava nada.
    atual = (
        DivisaoDespesa.transacao_id.is_(None)
        if lido is None
        else DivisaoDespesa.transacao_id == lido
    )
    try:
        alteradas = db.execute(
            update(DivisaoDespesa)
            .where(DivisaoDespesa.id == despesa.id, atual)
            .values(**valores)
            .execution_options(synchronize_session=False)
        ).rowcount
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(_JA_VINCULADA) from exc
    if alteradas != 1:
        db.rollback()
        raise ConflictError("o vínculo da divisão mudou; recarregue e tente de novo")
    if reajustadas is not None:
        repo.definir_participantes(despesa.id, reajustadas)  # mesmo commit do vínculo
    _commit_vinculo(db)
    db.refresh(despesa)
    return enriquecer(db, usuario_id, despesa)


# ponytail: janela/teto fixos — a lista é sugestão; o usuário ainda pode deixar para depois.
_JANELA_CANDIDATAS = timedelta(days=7)
_LIMITE_CANDIDATAS = 20


def transacoes_candidatas(
    db: Session, usuario_id: int, valor_centavos: int, data: datetime
) -> list[Transacao]:
    """Saídas do usuário ainda sem divisão em ±7 dias da data: mesmo valor primeiro, depois as
    mais próximas da data (RF03)."""
    valor = func.abs(
        func.coalesce(Transacao.amount_in_account_currency_centavos, Transacao.amount_centavos)
    )
    vinculadas = select(DivisaoDespesa.transacao_id).where(DivisaoDespesa.transacao_id.is_not(None))
    linhas = db.scalars(
        select(Transacao)
        .where(
            Transacao.usuario_id == usuario_id,
            Transacao.type == "DEBIT",
            Transacao.eh_transferencia.is_(False),
            Transacao.date >= data - _JANELA_CANDIDATAS,
            Transacao.date <= data + _JANELA_CANDIDATAS,
            Transacao.id.not_in(vinculadas),
        )
        .order_by(case((valor == valor_centavos, 0), else_=1), Transacao.date.desc())
        .limit(_LIMITE_CANDIDATAS * 5)
    ).all()
    alvo = data if data.tzinfo else data.replace(tzinfo=UTC)

    def chave(tx: Transacao) -> tuple[bool, timedelta]:
        quando = tx.date if tx.date.tzinfo else tx.date.replace(tzinfo=UTC)
        efetivo = tx.amount_in_account_currency_centavos or tx.amount_centavos
        return abs(efetivo) != valor_centavos, abs(quando - alvo)

    return sorted(linhas, key=chave)[:_LIMITE_CANDIDATAS]


def atualizar(
    db: Session, usuario_id: int, despesa_id: int, payload: DivisaoDespesaUpdate
) -> DivisaoDespesaRead:
    repo = DivisaoDespesaRepository(db, usuario_id)
    despesa = repo.obter_como_criador(despesa_id)
    if despesa is None:
        raise NotFoundError("despesa não encontrada")

    campos = payload.model_dump(exclude_unset=True)
    pago_por_usuario_id = campos.get("pago_por_usuario_id", despesa.pago_por_usuario_id)
    modo_divisao = campos.get("modo_divisao", despesa.modo_divisao)
    valor_total_centavos = campos.get("valor_total_centavos", despesa.valor_total_centavos)
    participantes_payload = campos.pop("participantes", None)
    partes_payload = campos.pop("partes", None)
    atuais = repo.participantes(despesa.id)
    partes = [(p["usuario_id"], p["valor"]) for p in partes_payload] if partes_payload else None
    if modo_divisao in MODOS_COM_PARTES and partes is None:
        # Sem fatias novas: só dá para reaproveitar as atuais no mesmo modo e mesmas pessoas. Em
        # `porcentagem` elas seguem valendo para um total novo; em `valor` a soma é revalidada.
        if modo_divisao != despesa.modo_divisao or participantes_payload is not None:
            raise ValidationError("informe a parte de cada pessoa")
        partes = [
            (p.usuario_id, p.percentual_bp if modo_divisao == "porcentagem" else p.valor_centavos)
            for p in atuais
        ]
    if participantes_payload is None:
        participantes_payload = [p.usuario_id for p in atuais]
    linhas = _linhas(
        db,
        pago_por_usuario_id,
        modo_divisao,
        valor_total_centavos,
        participantes_payload,
        partes,
    )
    if campos.get("data", despesa.data) is None:
        campos.pop("data")  # `data` é NOT NULL: null no PATCH = "não mexer"
    if pago_por_usuario_id != despesa.pago_por_usuario_id:
        # A transação vinculada era do pagador anterior — não representa mais a despesa.
        campos["transacao_id"], campos["sem_transacao"] = None, False
    if "categoria_id" in campos:
        _validar_categoria(db, campos["categoria_id"])
    repo.atualizar(despesa, **campos)
    repo.definir_participantes(despesa.id, linhas)
    commit(db)
    db.refresh(despesa)
    return enriquecer(db, usuario_id, despesa)


# --- divisão na lista de transações (RF08–RF10) --------------------------------------------


def por_transacao(
    db: Session, usuario_id: int, transacao_ids: list[int]
) -> dict[int, DivisaoDaTransacao]:
    """{transacao_id: resumo da divisão} das transações da página (uma consulta)."""
    if not transacao_ids:
        return {}
    outros = aliased(DivisaoParticipante)
    linhas = db.execute(
        select(
            DivisaoDespesa.transacao_id,
            DivisaoDespesa.id,
            DivisaoDespesa.valor_total_centavos,
            func.coalesce(func.sum(outros.valor_centavos), 0),
            VALOR_EFETIVO,
        )
        .join(Transacao, Transacao.id == DivisaoDespesa.transacao_id)
        .outerjoin(
            outros, and_(outros.divisao_id == DivisaoDespesa.id, outros.usuario_id != usuario_id)
        )
        .where(
            DivisaoDespesa.transacao_id.in_(transacao_ids),
            DivisaoDespesa.pago_por_usuario_id == usuario_id,
        )
        .group_by(
            DivisaoDespesa.transacao_id,
            DivisaoDespesa.id,
            DivisaoDespesa.valor_total_centavos,
            VALOR_EFETIVO,
        )
    ).all()
    # Mesma conta de `gasto_usuario.VALOR_USUARIO`: transação − parte dos outros, mínimo 0.
    return {
        tx_id: DivisaoDaTransacao(
            id=d_id,
            valor_total_centavos=total,
            outros_centavos=int(dos_outros),
            minha_parte_centavos=max(abs(valor) - int(dos_outros), 0),
        )
        for tx_id, d_id, total, dos_outros, valor in linhas
    }


def expr_pendente(usuario_id: int, corte: datetime | None):
    """Divisão paga por mim, sem transação e sem "fora do banco" (RF10)."""
    cond = and_(
        DivisaoDespesa.pago_por_usuario_id == usuario_id,
        DivisaoDespesa.transacao_id.is_(None),
        DivisaoDespesa.sem_transacao.is_(False),
    )
    return cond if corte is None else and_(cond, DivisaoDespesa.data >= corte)


def select_lancamentos(
    usuario_id: int,
    *,
    corte: datetime | None,
    inicio: datetime | None = None,
    fim: datetime | None = None,
    categoria_id: str | None = None,
    busca: str | None = None,
    pendente: bool | None = None,
):
    """Chaves (origem=1, id, data, valor p/ ordenar) dos lançamentos de divisão do usuário: pagas
    por outra pessoa com parte minha > 0, e pagas por mim sem transação (pendentes ou "fora do
    banco"). O valor de ordenação segue a convenção de saída (negativo)."""
    minha = aliased(DivisaoParticipante, name="minha_linha")
    parte = func.coalesce(minha.valor_centavos, 0)
    pendente_expr = expr_pendente(usuario_id, None)
    exibido = case((pendente_expr, DivisaoDespesa.valor_total_centavos), else_=parte)
    stmt = (
        select(
            literal(1).label("origem"),
            DivisaoDespesa.id.label("id"),
            DivisaoDespesa.data.label("data"),
            (-exibido).label("valor"),
        )
        .outerjoin(
            minha, and_(minha.divisao_id == DivisaoDespesa.id, minha.usuario_id == usuario_id)
        )
        .where(
            DivisaoDespesa.arquivada.is_(False),
            or_(
                and_(DivisaoDespesa.pago_por_usuario_id != usuario_id, parte > 0),
                and_(
                    DivisaoDespesa.pago_por_usuario_id == usuario_id,
                    DivisaoDespesa.transacao_id.is_(None),
                ),
            ),
        )
    )
    if inicio is not None:
        stmt = stmt.where(DivisaoDespesa.data >= inicio)
    if fim is not None:
        stmt = stmt.where(DivisaoDespesa.data < fim)
    if categoria_id is not None:
        stmt = stmt.outerjoin(Categoria, Categoria.pluggy_id == DivisaoDespesa.categoria_id).where(
            categoria_da_divisao(usuario_id) == categoria_id
        )
    if busca:
        stmt = stmt.where(DivisaoDespesa.descricao.ilike(f"%{_escape_like(busca)}%", escape="\\"))
    if pendente is not None:
        cond = expr_pendente(usuario_id, corte)
        stmt = stmt.where(cond if pendente else ~cond)
    return stmt


def lancamentos(
    db: Session, usuario_id: int, ids: list[int], corte: datetime | None
) -> dict[int, DivisaoLancamento]:
    """Hidrata os lançamentos da página (ids vindos de `select_lancamentos`)."""
    if not ids:
        return {}
    minha = aliased(DivisaoParticipante, name="minha_linha")
    linhas = db.execute(
        select(
            DivisaoDespesa,
            func.coalesce(minha.valor_centavos, 0),
            Usuario.nome,
            categoria_da_divisao(usuario_id),
        )
        .outerjoin(
            minha, and_(minha.divisao_id == DivisaoDespesa.id, minha.usuario_id == usuario_id)
        )
        .join(Usuario, Usuario.id == DivisaoDespesa.pago_por_usuario_id)
        .outerjoin(Categoria, Categoria.pluggy_id == DivisaoDespesa.categoria_id)
        .where(DivisaoDespesa.id.in_(ids))
    ).all()
    corte_aware = corte if corte is None or corte.tzinfo else corte.replace(tzinfo=UTC)
    resultado = {}
    for d, parte, pagador, categoria in linhas:
        data = d.data if d.data.tzinfo else d.data.replace(tzinfo=UTC)
        pago_por_mim = d.pago_por_usuario_id == usuario_id
        resultado[d.id] = DivisaoLancamento(
            divisao_id=d.id,
            data=data,
            descricao=d.descricao,
            categoria_id=categoria,
            valor_total_centavos=d.valor_total_centavos,
            minha_parte_centavos=parte,
            pago_por_nome=pagador,
            pago_por_mim=pago_por_mim,
            sem_transacao=d.sem_transacao,
            pendente=pago_por_mim
            and d.transacao_id is None
            and not d.sem_transacao
            and (corte_aware is None or data >= corte_aware),
        )
    return resultado


def pendentes(
    db: Session, usuario_id: int, corte: datetime | None, fim: datetime, limite: int
) -> tuple[list[DivisaoDespesa], int]:
    """Divisões pendentes de vínculo (RF10/RF11) com data antes de `fim` (mesmo corte de "hoje"
    da seção de transações), mais recentes primeiro, + total."""
    filtros = (
        DivisaoDespesa.arquivada.is_(False),
        DivisaoDespesa.data < fim,
        expr_pendente(usuario_id, corte),
    )
    total = db.scalar(select(func.count()).select_from(DivisaoDespesa).where(*filtros)) or 0
    itens = db.scalars(
        select(DivisaoDespesa)
        .where(*filtros)
        .order_by(DivisaoDespesa.data.desc(), DivisaoDespesa.id.desc())
        .limit(limite)
    ).all()
    return list(itens), total


def remover(db: Session, usuario_id: int, despesa_id: int) -> None:
    repo = DivisaoDespesaRepository(db, usuario_id)
    despesa = repo.obter_como_criador(despesa_id)
    if despesa is None:
        raise NotFoundError("despesa não encontrada")
    repo.remover(despesa)


def marcar_quitada(
    db: Session, usuario_id: int, despesa_id: int, quitada: bool
) -> DivisaoDespesaRead:
    """Criador, pagador ou qualquer participante pode quitar/reabrir (não exclusivo do criador)."""
    repo = DivisaoDespesaRepository(db, usuario_id)
    despesa = repo.obter(despesa_id)
    if despesa is None:
        raise NotFoundError("despesa não encontrada")
    despesa.quitada = quitada
    commit(db)
    db.refresh(despesa)
    return enriquecer(db, usuario_id, despesa)


def saldos_por_pessoa(
    db: Session, usuario_id: int, *, incluir_zerados: bool = False
) -> dict[int, int]:
    """{contraparte_usuario_id: saldo_centavos} — positivo = me devem, negativo = eu devo.

    Só despesas não quitadas entram na soma (mesmo padrão de `valores_guardados` em
    app/services/objetivo.py: agregação simples, sem tabela própria de saldo).
    """
    saldos: dict[int, int] = {}

    # Despesas em que eu paguei: cada participante que não sou eu me deve o próprio valor.
    a_receber = db.execute(
        select(DivisaoParticipante.usuario_id, DivisaoParticipante.valor_centavos)
        .join(DivisaoDespesa, DivisaoDespesa.id == DivisaoParticipante.divisao_id)
        .where(
            DivisaoDespesa.pago_por_usuario_id == usuario_id,
            DivisaoDespesa.quitada.is_(False),
            DivisaoParticipante.usuario_id != usuario_id,
        )
    ).all()
    for contraparte_id, valor in a_receber:
        saldos[contraparte_id] = saldos.get(contraparte_id, 0) + valor

    # Despesas em que outro pagou e eu sou participante: eu devo meu valor a quem pagou.
    a_pagar = db.execute(
        select(DivisaoDespesa.pago_por_usuario_id, DivisaoParticipante.valor_centavos)
        .join(DivisaoDespesa, DivisaoDespesa.id == DivisaoParticipante.divisao_id)
        .where(
            DivisaoParticipante.usuario_id == usuario_id,
            DivisaoDespesa.quitada.is_(False),
            DivisaoDespesa.pago_por_usuario_id != usuario_id,
        )
    ).all()
    for contraparte_id, valor in a_pagar:
        saldos[contraparte_id] = saldos.get(contraparte_id, 0) - valor

    if incluir_zerados:
        return saldos
    return {contraparte_id: saldo for contraparte_id, saldo in saldos.items() if saldo != 0}


def _saldos_efetivos(
    db: Session, usuario_id: int, *, incluir_zerados: bool = False
) -> dict[int, int]:
    """Saldos por contraparte já aplicando o toggle de otimização (§4.11-otimização) — único
    ponto de decisão "otimizado vs bruto", usado tanto por `resumo` quanto por `pessoas` pra
    nunca ficarem inconsistentes entre si."""
    if configuracao_service.otimizacao_divisao_ativa(db):
        saldos = divisao_otimizacao.saldos_otimizados_para_usuario(db, usuario_id)
    else:
        saldos = saldos_por_pessoa(db, usuario_id, incluir_zerados=True)
    if incluir_zerados:
        return saldos
    return {uid: s for uid, s in saldos.items() if s != 0}


def resumo(db: Session, usuario_id: int) -> ResumoDivisoes:
    saldos = _saldos_efetivos(db, usuario_id)
    a_receber = [s for s in saldos.values() if s > 0]
    a_pagar = [s for s in saldos.values() if s < 0]
    return ResumoDivisoes(
        saldo_a_receber_centavos=sum(a_receber),
        pessoas_a_receber=len(a_receber),
        saldo_a_pagar_centavos=-sum(a_pagar),
        pessoas_a_pagar=len(a_pagar),
        saldo_total_centavos=sum(saldos.values()),
    )


def _recencia(pessoa: PessoaDivisao) -> datetime:
    """Chave de ordenação por atividade — sempre *aware*, para os dois dialetos.

    O Postgres devolve `TIMESTAMPTZ` com fuso e o SQLite devolve naive (mesmo ajuste de
    `current_user`/`sync`). Como quem não tem atividade cai no `datetime.min`, sem normalizar os
    dois lados a ordenação mistura naive e aware e levanta `TypeError` — só no Postgres, que é
    justamente onde o self-hosted roda.
    """
    quando = pessoa.ultima_atividade
    if quando is None:
        return datetime.min.replace(tzinfo=UTC)
    return quando if quando.tzinfo is not None else quando.replace(tzinfo=UTC)


def pessoas(db: Session, usuario_id: int) -> list[PessoaDivisao]:
    """Toda contraparte relevante: quem já dividiu uma despesa comigo (mesmo já quitada/
    arquivada) OU quem eu convidei, mesmo que ainda não exista nenhuma despesa em comum —
    senão a pessoa "some" da aba Pessoas logo após ser convidada. Alimenta a aba Pessoas."""
    repo = DivisaoDespesaRepository(db, usuario_id)
    despesas = repo.visiveis()

    despesa_ids = {d.id for d in despesas}
    participantes_por_despesa: dict[int, list[int]] = {}
    for divisao_id, part_usuario_id in db.execute(
        select(DivisaoParticipante.divisao_id, DivisaoParticipante.usuario_id).where(
            DivisaoParticipante.divisao_id.in_(despesa_ids)
        )
    ).all():
        participantes_por_despesa.setdefault(divisao_id, []).append(part_usuario_id)

    ultima_atividade: dict[int, datetime | None] = {}

    def _marcar(contraparte_id: int, quando: datetime) -> None:
        anterior = ultima_atividade.get(contraparte_id)
        if anterior is None or quando > anterior:
            ultima_atividade[contraparte_id] = quando

    for despesa in despesas:
        envolvidos = {despesa.criado_por_usuario_id, despesa.pago_por_usuario_id}
        envolvidos |= set(participantes_por_despesa.get(despesa.id, []))
        envolvidos.discard(usuario_id)
        for contraparte_id in envolvidos:
            _marcar(contraparte_id, despesa.atualizado_em)

    convidados = db.scalars(
        select(ConviteUsuario).where(ConviteUsuario.criado_por_usuario_id == usuario_id)
    ).all()
    for convite in convidados:
        _marcar(convite.usuario_id, convite.criado_em)

    saldos = _saldos_efetivos(db, usuario_id, incluir_zerados=True)
    # Com otimização ligada, uma aresta pode apontar pra alguém fora da rede de despesas
    # diretas do usuário (ex.: a dívida de A com B foi "roteada" pra C via simplificação) — sem
    # isso, essa contraparte nunca apareceria na lista, mesmo tendo saldo real (§4.11-otimização).
    # Sem despesa/convite em comum não há timestamp de atividade pra ela: cai no fim da lista
    # (`ultima_atividade=None`, tratado no sort abaixo).
    for contraparte_id, saldo in saldos.items():
        if saldo != 0 and contraparte_id not in ultima_atividade:
            ultima_atividade[contraparte_id] = None

    if not ultima_atividade:
        return []

    usuarios = {
        u.id: u
        for u in db.scalars(select(Usuario).where(Usuario.id.in_(ultima_atividade.keys()))).all()
    }
    resultado = [
        PessoaDivisao(
            usuario_id=contraparte_id,
            nome=usuarios[contraparte_id].nome,
            avatar=usuarios[contraparte_id].avatar,
            status="usuario" if usuarios[contraparte_id].senha_hash else "so_divisao",
            saldo_centavos=saldos.get(contraparte_id, 0),
            ultima_atividade=quando,
        )
        for contraparte_id, quando in ultima_atividade.items()
        if contraparte_id in usuarios
    ]
    resultado.sort(key=_recencia, reverse=True)
    return resultado
