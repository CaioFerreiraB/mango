"""Divisão de contas (§4.11): rateio, saldos entre pessoas e leitura enriquecida.

`DivisaoDespesaRead` não é um `read_model` puro — `participantes` e `meu_saldo_centavos` são
calculados aqui em runtime, mesmo padrão de `enriquecer_um`/`listar` em `app/services/objetivo.py`.
Nada de `HTTPException`: erros de domínio (`app/exceptions.py`), traduzidos a HTTP no `main`.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exceptions import NotFoundError, ValidationError
from app.models.categoria import Categoria
from app.models.convite import ConviteUsuario
from app.models.divisao import DivisaoDespesa, DivisaoParticipante
from app.models.usuario import Usuario
from app.repositories.divisao import DivisaoDespesaRepository, EscopoDivisao
from app.schemas.divisao import (
    DivisaoDespesaCreate,
    DivisaoDespesaRead,
    DivisaoDespesaUpdate,
    DivisaoParticipanteRead,
    PessoaDivisao,
    ResumoDivisoes,
)
from app.services import configuracao as configuracao_service
from app.services import divisao_otimizacao


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

    existentes = set(db.scalars(select(Usuario.id).where(Usuario.id.in_(ids_a_validar))).all())
    faltando = ids_a_validar - existentes
    if faltando:
        raise NotFoundError(f"usuário(s) inexistente(s): {sorted(faltando)}")

    return [devedor_id] if modo == "integral" else sorted(ids_a_validar)


def _validar_categoria(db: Session, categoria_id: str | None) -> None:
    if categoria_id is not None and db.get(Categoria, categoria_id) is None:
        raise NotFoundError("categoria não encontrada")


def _rateio(
    valor_total_centavos: int, modo: str, pago_por_usuario_id: int, participantes_ids: list[int]
) -> list[tuple[int, int]]:
    """[(usuario_id, valor_centavos)] — resto da divisão vai para os primeiros ids (decisão)."""
    if modo == "integral":
        return [(participantes_ids[0], valor_total_centavos)]
    ids = sorted(participantes_ids)
    base, resto = divmod(valor_total_centavos, len(ids))
    return [(uid, base + 1 if i < resto else base) for i, uid in enumerate(ids)]


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


def criar(db: Session, usuario_id: int, payload: DivisaoDespesaCreate) -> DivisaoDespesaRead:
    ids_validados = _validar_participantes(
        db, payload.pago_por_usuario_id, payload.modo_divisao, payload.participantes
    )
    _validar_categoria(db, payload.categoria_id)
    repo = DivisaoDespesaRepository(db, usuario_id)
    despesa = repo.criar(
        pago_por_usuario_id=payload.pago_por_usuario_id,
        descricao=payload.descricao,
        categoria_id=payload.categoria_id,
        valor_total_centavos=payload.valor_total_centavos,
        modo_divisao=payload.modo_divisao,
        quitada=False,
        arquivada=False,
    )
    linhas = _rateio(
        payload.valor_total_centavos,
        payload.modo_divisao,
        payload.pago_por_usuario_id,
        ids_validados,
    )
    repo.definir_participantes(despesa.id, linhas)
    db.commit()
    db.refresh(despesa)
    return enriquecer(db, usuario_id, despesa)


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
    if participantes_payload is None:
        participantes_payload = [p.usuario_id for p in repo.participantes(despesa.id)]

    ids_validados = _validar_participantes(
        db, pago_por_usuario_id, modo_divisao, participantes_payload
    )
    if "categoria_id" in campos:
        _validar_categoria(db, campos["categoria_id"])
    repo.atualizar(despesa, **campos)
    linhas = _rateio(valor_total_centavos, modo_divisao, pago_por_usuario_id, ids_validados)
    repo.definir_participantes(despesa.id, linhas)
    db.commit()
    db.refresh(despesa)
    return enriquecer(db, usuario_id, despesa)


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
    db.commit()
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
