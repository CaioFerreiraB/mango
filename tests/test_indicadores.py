"""Indicadores de mercado (Fase 3, §4.9) com httpx.MockTransport — nada de rede no CI.

Cobre: composição do CDI (dias úteis + forward-fill), degrau mensal do IPCA, variação do
IBOV, lista disponível condicionada ao token do brapi, cache com TTL e erro redigido.
"""

from datetime import date, datetime

import httpx
import pytest

from app.config import settings
from app.services import indicadores
from app.services.indicadores import IndicadorError
from app.services.periodo import SP


@pytest.fixture(autouse=True)
def _isolado(monkeypatch):
    indicadores._cache.clear()
    yield
    indicadores._cache.clear()
    indicadores._transport = None


def _usar(monkeypatch, respostas: dict[str, object], chamadas: list | None = None):
    """Instala um MockTransport que casa trechos de URL com corpos JSON."""

    def handler(request: httpx.Request) -> httpx.Response:
        if chamadas is not None:
            chamadas.append(request.url.path)
        for trecho, corpo in respostas.items():
            if trecho in str(request.url):
                return httpx.Response(200, json=corpo)
        return httpx.Response(500, json={})

    monkeypatch.setattr(indicadores, "_transport", httpx.MockTransport(handler))


def test_cdi_compoe_dias_uteis_com_forward_fill(monkeypatch):
    _usar(
        monkeypatch,
        {
            "bcdata.sgs.12": [
                {"data": "01/07/2026", "valor": "0.05"},
                {"data": "02/07/2026", "valor": "0.05"},
                # 03–05/07 sem observação (fim de semana) → forward-fill
            ]
        },
    )
    pontos = dict(indicadores.serie("cdi", date(2026, 7, 1), date(2026, 7, 5)))
    assert len(pontos) == 5
    assert pontos[date(2026, 7, 1)] == pytest.approx(0.05)
    assert pontos[date(2026, 7, 2)] == pytest.approx(0.100025)  # (1.0005² − 1) × 100
    assert pontos[date(2026, 7, 5)] == pytest.approx(0.100025)  # fill


def test_ipca_entra_como_degrau_mensal(monkeypatch):
    _usar(
        monkeypatch,
        {
            "bcdata.sgs.433": [
                {"data": "01/06/2026", "valor": "0.50"},
                {"data": "01/07/2026", "valor": "0.30"},
            ]
        },
    )
    pontos = dict(indicadores.serie("ipca", date(2026, 6, 1), date(2026, 7, 2)))
    assert pontos[date(2026, 6, 1)] == pytest.approx(0.5)
    assert pontos[date(2026, 6, 15)] == pytest.approx(0.5)  # degrau segura o mês
    assert pontos[date(2026, 7, 1)] == pytest.approx(0.8015)  # (1.005 × 1.003 − 1) × 100


def test_ibov_variacao_sobre_primeiro_fechamento(monkeypatch):
    monkeypatch.setattr(settings, "brapi_token", "tok")
    d1, d2 = date(2026, 7, 1), date(2026, 7, 2)
    ts = lambda d: int(datetime(d.year, d.month, d.day, 13, tzinfo=SP).timestamp())  # noqa: E731
    _usar(
        monkeypatch,
        {
            "/quote/": {
                "results": [
                    {
                        "historicalDataPrice": [
                            {"date": ts(d1), "close": 100000},
                            {"date": ts(d2), "close": 110000},
                        ]
                    }
                ]
            }
        },
    )
    pontos = dict(indicadores.serie("ibov", d1, d2))
    assert pontos[d1] == pytest.approx(0.0)
    assert pontos[d2] == pytest.approx(10.0)


def test_disponiveis_condicionado_ao_token(monkeypatch):
    monkeypatch.setattr(settings, "brapi_token", "")
    assert [i["codigo"] for i in indicadores.disponiveis()] == ["cdi", "selic", "ipca"]
    monkeypatch.setattr(settings, "brapi_token", "tok")
    assert "ibov" in [i["codigo"] for i in indicadores.disponiveis()]


def test_cache_evita_refetch(monkeypatch):
    chamadas: list[str] = []
    _usar(monkeypatch, {"bcdata.sgs.12": [{"data": "01/07/2026", "valor": "0.05"}]}, chamadas)
    indicadores.serie("cdi", date(2026, 7, 1), date(2026, 7, 2))
    indicadores.serie("cdi", date(2026, 7, 1), date(2026, 7, 2))
    assert len(chamadas) == 1  # segunda leitura sai do cache


def test_erro_http_vira_indicador_error_sem_vazar_token(monkeypatch):
    monkeypatch.setattr(settings, "brapi_token", "segredo-token")
    _usar(monkeypatch, {})  # tudo responde 500
    with pytest.raises(IndicadorError) as exc:
        indicadores.serie("ibov", date(2026, 7, 1), date(2026, 7, 2))
    assert "segredo-token" not in str(exc.value)  # mensagem redigida (URL sem query)
    with pytest.raises(IndicadorError):
        indicadores.serie("cdi", date(2026, 7, 1), date(2026, 7, 2))


def test_sgs_404_vira_serie_vazia(monkeypatch):
    # SGS responde 404 quando não há observação no intervalo (IPCA mensal em janela curta):
    # não deve derrubar o lote — série sai flat em 0% via forward-fill.
    monkeypatch.setattr(
        indicadores,
        "_transport",
        httpx.MockTransport(lambda req: httpx.Response(404, json={})),
    )
    pontos = dict(indicadores.serie("ipca", date(2026, 7, 17), date(2026, 7, 25)))
    assert len(pontos) == 9
    assert all(v == pytest.approx(0.0) for v in pontos.values())


def test_serie_indicador_desconhecido(monkeypatch):
    with pytest.raises(IndicadorError):
        indicadores.serie("nasdaq", date(2026, 7, 1), date(2026, 7, 2))


# --- rota -----------------------------------------------------------------------------


def test_rota_lista_e_valida(client_factory, usuario_a, monkeypatch):
    monkeypatch.setattr(settings, "brapi_token", "")
    client = client_factory(usuario_a)
    assert [i["codigo"] for i in client.get("/api/indicadores").json()] == [
        "cdi",
        "selic",
        "ipca",
    ]
    # código desconhecido e período invertido → 422 (validação de fronteira)
    r = client.get(
        "/api/indicadores/serie",
        params={"codigos": "cdi,nasdaq", "inicio": "2026-07-01", "fim": "2026-07-02"},
    )
    assert r.status_code == 422
    r = client.get(
        "/api/indicadores/serie",
        params={"codigos": "cdi", "inicio": "2026-07-02", "fim": "2026-07-01"},
    )
    assert r.status_code == 422


def test_rota_serie_pula_indicador_que_falha(client_factory, usuario_a, monkeypatch):
    # IBOV (brapi) não casa no mock → 500 → IndicadorError; CDI (BCB) responde. A rota deve
    # devolver 200 só com o CDI, sem derrubar o pedido inteiro por causa do IBOV.
    monkeypatch.setattr(settings, "brapi_token", "tok")
    _usar(monkeypatch, {"bcdata.sgs.12": [{"data": "01/07/2026", "valor": "0.05"}]})
    client = client_factory(usuario_a)
    r = client.get(
        "/api/indicadores/serie",
        params={"codigos": "cdi,ibov", "inicio": "2026-07-01", "fim": "2026-07-02"},
    )
    assert r.status_code == 200
    assert [s["codigo"] for s in r.json()] == ["cdi"]


def test_rota_serie_502_quando_todos_falham(client_factory, usuario_a, monkeypatch):
    # Nada casa no mock → todos os indicadores falham → 502 (indisponibilidade real da fonte).
    _usar(monkeypatch, {})
    client = client_factory(usuario_a)
    r = client.get(
        "/api/indicadores/serie",
        params={"codigos": "cdi,selic", "inicio": "2026-07-01", "fim": "2026-07-02"},
    )
    assert r.status_code == 502
