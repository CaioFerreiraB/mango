"""Despesas fixas (docs/dev/despesas-fixas.md): agenda de vencimentos, materialização lazy,
situação/atrasos, resumo do mês e vínculo com transação.

`vencimentos` é a ÚNICA fonte de datas (RF03). Os vencimentos são materializados sob demanda —
todos até hoje + o próximo futuro (RF05) — em toda leitura, no job de avisos e no vínculo.
"""

from __future__ import annotations

from calendar import monthrange
from collections.abc import Iterator
from datetime import date, timedelta

from sqlalchemy import delete, exists, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.despesa_fixa import DespesaFixa, DespesaFixaOcorrencia
from app.models.transacao import Transacao
from app.security.current_user import _aware
from app.services.periodo import SP

_PASSO_MESES = {"mensal": 1, "trimestral": 3, "semestral": 6, "anual": 12}
_PASSO_DIAS = {"semanal": 7, "quinzenal": 14}

# Campos cuja mudança refaz os vencimentos futuros em aberto (RF08).
CAMPOS_AGENDA = frozenset({"valor_centavos", "frequencia", "dia_vencimento", "inicio", "fim"})


def _no_mes(ano: int, mes: int, dia: int) -> date:
    return date(ano, mes, min(dia, monthrange(ano, mes)[1]))


def _somar_meses(ano: int, mes: int, n: int) -> tuple[int, int]:
    indice = ano * 12 + mes - 1 + n
    return indice // 12, indice % 12 + 1


def vencimentos(frequencia: str, dia: int, inicio: date, fim: date | None) -> Iterator[date]:
    """Datas de vencimento em ordem, a partir de `inicio`, até `fim` (ou sem fim). RF03.

    Mensal+: o dia é re-limitado a cada mês (31 → 28/29 em fevereiro → 31 em março), por isso é
    calculado do 1º vencimento + k·passo, nunca da data anterior. Semanal/quinzenal: +7/+14 dias."""
    primeiro = _no_mes(inicio.year, inicio.month, dia)
    if primeiro < inicio:
        primeiro = _no_mes(*_somar_meses(inicio.year, inicio.month, 1), dia)
    k = 0
    while True:
        if frequencia in _PASSO_DIAS:
            atual = primeiro + timedelta(days=_PASSO_DIAS[frequencia] * k)
        else:
            atual = _no_mes(
                *_somar_meses(primeiro.year, primeiro.month, _PASSO_MESES[frequencia] * k), dia
            )
        if fim is not None and atual > fim:
            return
        yield atual
        k += 1


def _agenda(despesa: DespesaFixa) -> Iterator[date]:
    """Vencimentos da despesa a partir do piso de geração (`retomada_em`, RF09)."""
    piso = despesa.retomada_em or date.min
    for v in vencimentos(despesa.frequencia, despesa.dia_vencimento, despesa.inicio, despesa.fim):
        if v >= piso:
            yield v


def piso_na_criacao(inicio: date, hoje: date) -> date | None:
    """Despesa que começa antes do mês corrente só é acompanhada a partir dele (RF04): uma
    temporária iniciada em março não nasce com oito atrasos."""
    mes_atual = hoje.replace(day=1)
    return mes_atual if inicio < mes_atual else None


def materializar(db: Session, usuario_id: int, hoje: date) -> int:
    """Cria os vencimentos que faltam (até hoje + o próximo futuro em aberto) das despesas ativas.
    Idempotente e seguro sob concorrência: a UNIQUE(despesa, vencimento) barra duplicata e a
    corrida perdida só é descartada (RF05). Devolve quantos criou."""
    despesas = db.scalars(
        select(DespesaFixa).where(DespesaFixa.usuario_id == usuario_id, DespesaFixa.ativa)
    ).all()
    if not despesas:
        return 0
    status = {
        (despesa_id, vencimento): st
        for despesa_id, vencimento, st in db.execute(
            select(
                DespesaFixaOcorrencia.despesa_fixa_id,
                DespesaFixaOcorrencia.vencimento,
                DespesaFixaOcorrencia.status,
            ).where(DespesaFixaOcorrencia.usuario_id == usuario_id)
        )
    }
    novas = []
    for despesa in despesas:
        for v in _agenda(despesa):
            st = status.get((despesa.id, v))
            if st is None:
                novas.append(_nova(despesa, v))
            # Para no 1º futuro EM ABERTO: futuro já pago (antecipado) ou pulado não conta como
            # "próximo vencimento" — segue até achar um que ainda está por pagar.
            if v > hoje and st in (None, "aberta"):
                break
    if not novas:
        return 0
    db.add_all(novas)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # outra requisição materializou junto; a próxima leitura já vê tudo
        return 0
    return len(novas)


def _nova(despesa: DespesaFixa, vencimento: date) -> DespesaFixaOcorrencia:
    return DespesaFixaOcorrencia(
        usuario_id=despesa.usuario_id,
        despesa_fixa_id=despesa.id,
        vencimento=vencimento,
        valor_centavos=despesa.valor_centavos,
        status="aberta",
    )


def _sem_transacao():
    return ~exists().where(Transacao.despesa_fixa_ocorrencia_id == DespesaFixaOcorrencia.id)


def regenerar_futuras(db: Session, despesa: DespesaFixa, hoje: date) -> None:
    """Apaga os vencimentos em aberto de hoje em diante sem transação (RF08); a próxima
    materialização os recria com a agenda/valor novos. O histórico não muda. Não comita."""
    db.execute(
        delete(DespesaFixaOcorrencia)
        .where(
            DespesaFixaOcorrencia.despesa_fixa_id == despesa.id,
            DespesaFixaOcorrencia.status == "aberta",
            DespesaFixaOcorrencia.vencimento >= hoje,
            _sem_transacao(),
        )
        .execution_options(synchronize_session=False)
    )


# --- situação ----------------------------------------------------------------------------------


def situacao_ocorrencia(oc: DespesaFixaOcorrencia, hoje: date) -> str:
    """Status para exibição: o guardado, com `aberta` desdobrada em atrasada/vence_hoje (RF06)."""
    if oc.status != "aberta":
        return oc.status
    if oc.vencimento < hoje:
        return "atrasada"
    return "vence_hoje" if oc.vencimento == hoje else "aberta"


def indicadores(despesa: DespesaFixa, ocorrencias: list[DespesaFixaOcorrencia], hoje: date) -> dict:
    """`proximo_vencimento`, `qtd_atrasos` e `situacao` (o mais grave) de uma despesa (RF11)."""
    abertas = [o for o in ocorrencias if o.status == "aberta"]
    atrasos = sum(1 for o in abertas if o.vencimento < hoje)
    futuras = sorted(o.vencimento for o in abertas if o.vencimento >= hoje)
    do_mes = [
        o for o in ocorrencias if (o.vencimento.year, o.vencimento.month) == (hoje.year, hoje.month)
    ]
    if not despesa.ativa:
        situacao = "inativa"
    elif atrasos:
        situacao = "atrasada"
    elif futuras and futuras[0] == hoje:
        situacao = "vence_hoje"
    elif any(o.status == "aberta" for o in do_mes):
        situacao = "em_aberto"
    elif any(o.status == "paga" for o in do_mes):
        situacao = "paga"
    elif do_mes:
        situacao = "pulada"  # o mês todo foi pulado
    else:
        situacao = "em_dia"  # nenhum vencimento neste mês (trimestral, anual…)
    return {
        "proximo_vencimento": futuras[0] if futuras and despesa.ativa else None,
        "qtd_atrasos": atrasos if despesa.ativa else 0,
        "situacao": situacao,
    }


def ocorrencias_por_despesa(db: Session, usuario_id: int) -> dict[int, list[DespesaFixaOcorrencia]]:
    por: dict[int, list[DespesaFixaOcorrencia]] = {}
    for oc in db.scalars(
        select(DespesaFixaOcorrencia)
        .where(DespesaFixaOcorrencia.usuario_id == usuario_id)
        .order_by(DespesaFixaOcorrencia.vencimento)
    ):
        por.setdefault(oc.despesa_fixa_id, []).append(oc)
    return por


def qtd_transacoes(db: Session, ocorrencia_ids: list[int]) -> dict[int, int]:
    if not ocorrencia_ids:
        return {}
    return dict(
        db.execute(
            select(Transacao.despesa_fixa_ocorrencia_id, func.count())
            .where(Transacao.despesa_fixa_ocorrencia_id.in_(ocorrencia_ids))
            .group_by(Transacao.despesa_fixa_ocorrencia_id)
        ).all()
    )


def resumo(db: Session, usuario_id: int, hoje: date) -> dict:
    """Resumo do mês corrente das despesas ATIVAS (RF19): pagas/abertas do mês, atrasadas de
    qualquer mês, puladas, e os próximos 5 (atrasadas primeiro, depois as próximas em aberto)."""
    materializar(db, usuario_id, hoje)
    linhas = db.execute(
        select(DespesaFixaOcorrencia, DespesaFixa.descricao)
        .join(DespesaFixa, DespesaFixa.id == DespesaFixaOcorrencia.despesa_fixa_id)
        .where(DespesaFixaOcorrencia.usuario_id == usuario_id, DespesaFixa.ativa)
        .order_by(DespesaFixaOcorrencia.vencimento, DespesaFixaOcorrencia.id)
    ).all()

    def no_mes(oc: DespesaFixaOcorrencia) -> bool:
        return (oc.vencimento.year, oc.vencimento.month) == (hoje.year, hoje.month)

    total = {"pagas": [0, 0], "abertas": [0, 0], "atrasadas": [0, 0]}
    puladas = 0
    proximos_atrasados, proximos_abertos = [], []
    vistos: set[int] = set()  # um "próximo" por despesa (a semanal não ocupa a lista toda)
    for oc, descricao in linhas:
        sit = situacao_ocorrencia(oc, hoje)
        chave = {"paga": "pagas", "atrasada": "atrasadas"}.get(sit, "abertas")
        if sit == "atrasada" or (sit in ("paga", "aberta", "vence_hoje") and no_mes(oc)):
            total[chave][0] += 1
            total[chave][1] += oc.valor_centavos
        elif sit == "pulada" and no_mes(oc):
            puladas += 1
        item = {
            "ocorrencia_id": oc.id,
            "despesa_id": oc.despesa_fixa_id,
            "descricao": descricao,
            "vencimento": oc.vencimento,
            "valor_centavos": oc.valor_centavos,
            "situacao": sit,
        }
        if sit == "atrasada":
            proximos_atrasados.append(item)
        elif sit in ("aberta", "vence_hoje") and oc.despesa_fixa_id not in vistos:
            vistos.add(oc.despesa_fixa_id)
            proximos_abertos.append(item)
    tem_despesas = db.scalar(
        select(exists().where(DespesaFixa.usuario_id == usuario_id, DespesaFixa.ativa))
    )
    return {
        "mes": f"{hoje:%Y-%m}",
        "tem_despesas": bool(tem_despesas),
        **{k: {"qtd": q, "centavos": c} for k, (q, c) in total.items()},
        "puladas": puladas,
        "proximos": (proximos_atrasados + proximos_abertos)[:5],
    }


# --- vínculo com transação (RF12/RF13) ----------------------------------------------------------


def _alvo(db: Session, despesa: DespesaFixa) -> DespesaFixaOcorrencia | None:
    """Vencimento que a transação paga: o `aberto` mais antigo (atrasado primeiro); sem nenhum,
    o próximo ainda não gerado (pagamento antecipado). None se a agenda acabou (temporária)."""
    aberta = db.scalar(
        select(DespesaFixaOcorrencia)
        .where(
            DespesaFixaOcorrencia.despesa_fixa_id == despesa.id,
            DespesaFixaOcorrencia.status == "aberta",
        )
        .order_by(DespesaFixaOcorrencia.vencimento)
        .limit(1)
    )
    if aberta is not None:
        return aberta
    ultimo = db.scalar(
        select(func.max(DespesaFixaOcorrencia.vencimento)).where(
            DespesaFixaOcorrencia.despesa_fixa_id == despesa.id
        )
    )
    proximo = next((v for v in _agenda(despesa) if ultimo is None or v > ultimo), None)
    if proximo is None:
        return None
    oc = _nova(despesa, proximo)
    db.add(oc)
    db.flush()
    return oc


def travar_vinculo(db: Session, transacao_id: int, despesa_id: int | None) -> Transacao:
    """Serializa a troca de vínculo: lê o vínculo atual só DEPOIS de travar, até o commit.

    O UPDATE neutro é o que trava nos dois bancos (mesmo padrão de `operacoes.py`): no SQLite um
    `FOR UPDATE` é ignorado, mas a escrita pega o lock de escrita do banco; no Postgres trava a
    linha. A despesa também é travada (Postgres), para que transações DIFERENTES vinculadas à mesma
    despesa ao mesmo tempo não paguem o mesmo vencimento. Ordem fixa: transação → despesa."""
    db.execute(
        update(Transacao)
        .where(Transacao.id == transacao_id)
        .values(despesa_fixa_id=Transacao.despesa_fixa_id)
        .execution_options(synchronize_session=False)
    )
    if despesa_id is not None:
        db.execute(select(DespesaFixa.id).where(DespesaFixa.id == despesa_id).with_for_update())
    return db.scalars(
        select(Transacao)
        .where(Transacao.id == transacao_id)
        .execution_options(populate_existing=True)
    ).one()


def desvincular(db: Session, transacao: Transacao) -> None:
    """Tira a transação da despesa; o vencimento que ela pagava volta a `aberta` se nenhuma outra
    transação o paga. Não comita (o PATCH comita tudo junto)."""
    oid = transacao.despesa_fixa_ocorrencia_id
    transacao.despesa_fixa_id = None
    transacao.despesa_fixa_ocorrencia_id = None
    if oid is None:
        return
    db.flush()
    oc = db.get(DespesaFixaOcorrencia, oid)
    outra = db.scalar(select(exists().where(Transacao.despesa_fixa_ocorrencia_id == oid)))
    if oc is not None and oc.status == "paga" and not outra:
        oc.status, oc.pago_em = "aberta", None


def vincular(db: Session, transacao: Transacao, despesa: DespesaFixa) -> None:
    """Liga a transação à despesa e marca como paga o vencimento-alvo (RF12). Idempotente: a mesma
    despesa já vinculada não paga outro vencimento. Não comita."""
    if transacao.despesa_fixa_id == despesa.id and transacao.despesa_fixa_ocorrencia_id:
        return
    desvincular(db, transacao)
    transacao.despesa_fixa_id = despesa.id
    oc = _alvo(db, despesa)
    if oc is None:
        return
    oc.status = "paga"
    oc.pago_em = _aware(transacao.date).astimezone(SP).date()
    transacao.despesa_fixa_ocorrencia_id = oc.id
