"""Algoritmo puro de simplificação de dívidas (§4.11-otimização) — sem banco, só dicts/tuplas."""

from app.services.divisao_otimizacao import simplificar_dividas


def test_dict_vazio_devolve_lista_vazia():
    assert simplificar_dividas({}) == []


def test_saldos_zerados_nao_geram_arestas():
    assert simplificar_dividas({1: 0, 2: 0}) == []


def test_grafo_ja_minimo_nao_muda():
    # 1 deve 100 a 2 — já é a transação mínima possível.
    assert simplificar_dividas({1: -100, 2: 100}) == [(1, 2, 100)]


def test_simplifica_cadeia_a_deve_b_b_deve_c():
    """O exemplo do pedido: pessoa1 deve 10 a pessoa2, pessoa2 deve 10 a pessoa3. Saldo líquido
    de pessoa2 é zero (recebeu e pagou o mesmo valor) — some do grafo; sobra uma única aresta
    direta pessoa1 -> pessoa3."""
    saldos = {1: -1000, 2: 0, 3: 1000}  # pessoa2 já entra com saldo líquido zero
    assert simplificar_dividas(saldos) == [(1, 3, 1000)]


def test_um_credor_varios_devedores():
    # 2 e 3 devem 100 cada a 1.
    saldos = {1: 200, 2: -100, 3: -100}
    arestas = simplificar_dividas(saldos)
    assert set(arestas) == {(2, 1, 100), (3, 1, 100)}


def test_varios_credores_um_devedor():
    # 1 deve 100 a 2 e 100 a 3.
    saldos = {1: -200, 2: 100, 3: 100}
    arestas = simplificar_dividas(saldos)
    assert set(arestas) == {(1, 2, 100), (1, 3, 100)}


def test_empate_credor_e_devedor_desempata_deterministicamente_por_id():
    saldos = {10: -100, 20: -100, 30: 100, 40: 100}
    esperado = simplificar_dividas(saldos)
    # mesma entrada, mesma saída em chamadas repetidas — nada de depender de ordem de dict.
    for _ in range(5):
        assert simplificar_dividas(dict(saldos)) == esperado
    assert sum(v for *_, v in esperado) == 200


def test_soma_das_arestas_preserva_saldo_por_pessoa():
    saldos = {1: -300, 2: 500, 3: -400, 4: 200}
    arestas = simplificar_dividas(saldos)
    liquido: dict[int, int] = {}
    for devedor_id, credor_id, valor in arestas:
        liquido[devedor_id] = liquido.get(devedor_id, 0) - valor
        liquido[credor_id] = liquido.get(credor_id, 0) + valor
    assert liquido == saldos
