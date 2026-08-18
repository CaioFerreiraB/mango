"""Simplificação de dívidas em cadeia (debt simplification), estilo Splitwise (§4.11-otimização).

Escopo do "grupo" é a instância inteira (decisão de produto): todos os `usuario` que aparecem em
alguma `divisao_despesa` não quitada formam um único grafo, independente de quem está logado —
diferente de `saldos_por_pessoa` (app/services/divisao.py), que é sempre relativo a um usuário.

É só sugestão calculada em runtime — não persiste pagamento nem cria entidade de quitação nova
(decisão de produto). `simplificar_dividas` é pura (dict -> lista de arestas, sem I/O) — testável
isoladamente. As demais funções aqui buscam dados do banco e aplicam o algoritmo.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.divisao import DivisaoDespesa, DivisaoParticipante


def saldos_liquidos_instancia(db: Session) -> dict[int, int]:
    """{usuario_id: saldo_centavos} de TODA a instância (não relativo a nenhum usuário logado)
    — positivo = a receber, negativo = a pagar. Mesmo filtro de `saldos_por_pessoa`
    (app/services/divisao.py): só `quitada=False` importa; `arquivada` não afeta saldo."""
    saldos: dict[int, int] = {}
    linhas = db.execute(
        select(
            DivisaoDespesa.pago_por_usuario_id,
            DivisaoParticipante.usuario_id,
            DivisaoParticipante.valor_centavos,
        )
        .join(DivisaoDespesa, DivisaoDespesa.id == DivisaoParticipante.divisao_id)
        .where(DivisaoDespesa.quitada.is_(False))
    ).all()
    for pago_por_id, participante_id, valor in linhas:
        if participante_id == pago_por_id:
            continue  # a própria parte de quem pagou não é dívida com ninguém
        saldos[pago_por_id] = saldos.get(pago_por_id, 0) + valor
        saldos[participante_id] = saldos.get(participante_id, 0) - valor
    return {uid: s for uid, s in saldos.items() if s != 0}


def simplificar_dividas(saldos: dict[int, int]) -> list[tuple[int, int, int]]:
    """Algoritmo guloso clássico de min-cash-flow: a cada passo casa o maior credor com o maior
    devedor. NÃO é garantido minimizar o número de transações em todos os casos (esse problema é
    NP-difícil em geral) — é a mesma heurística prática usada por apps como Splitwise.

    Desempate determinístico por `usuario_id` (menor id primeiro) — resultado estável e
    reprodutível pra mesma entrada, importante pra não "trocar" a sugestão de pagamento a cada
    refresh só por causa da ordem de iteração de um dict.

    Entrada: {usuario_id: saldo_centavos} (positivo=credor, negativo=devedor; entradas com saldo
    0 são ignoradas). Saída: [(devedor_id, credor_id, valor_centavos)], só arestas com valor > 0.
    """
    credores = sorted(((uid, s) for uid, s in saldos.items() if s > 0), key=lambda t: (-t[1], t[0]))
    devedores = sorted(
        ((uid, -s) for uid, s in saldos.items() if s < 0), key=lambda t: (-t[1], t[0])
    )
    arestas: list[tuple[int, int, int]] = []
    i = j = 0
    while i < len(credores) and j < len(devedores):
        credor_id, credito = credores[i]
        devedor_id, debito = devedores[j]
        valor = min(credito, debito)
        if valor > 0:
            arestas.append((devedor_id, credor_id, valor))
        credito -= valor
        debito -= valor
        credores[i] = (credor_id, credito)
        devedores[j] = (devedor_id, debito)
        if credito == 0:
            i += 1
        if debito == 0:
            j += 1
    return arestas


def arestas_otimizadas(db: Session) -> list[tuple[int, int, int]]:
    return simplificar_dividas(saldos_liquidos_instancia(db))


def saldos_otimizados_para_usuario(db: Session, usuario_id: int) -> dict[int, int]:
    """{contraparte_usuario_id: saldo_centavos} filtrando as arestas do grafo simplificado que
    envolvem `usuario_id` — mesmo formato de saída de `saldos_por_pessoa` (positivo = me devem,
    negativo = eu devo), pra dar drop-in nos consumidores existentes (`resumo`/`pessoas`)."""
    saldos: dict[int, int] = {}
    for devedor_id, credor_id, valor in arestas_otimizadas(db):
        if devedor_id == usuario_id:
            saldos[credor_id] = saldos.get(credor_id, 0) - valor
        elif credor_id == usuario_id:
            saldos[devedor_id] = saldos.get(devedor_id, 0) + valor
    return saldos
