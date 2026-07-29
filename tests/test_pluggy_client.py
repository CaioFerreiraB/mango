"""Cliente HTTP do Pluggy — paginação por cursor do /v2/transactions (sem rede).

Regressão: o `next` do v2 vem relativo e só-query (`?accountId=…&after=…`), sem o path.
O cursor tem de preservar `/v2/transactions`; se cair na raiz, o Pluggy responde 403 e o
sync inteiro quebra (só dispara com >1 página de transações).
"""

from datetime import date

import httpx

from app.pluggy.client import PluggyClient


def _client(handler) -> PluggyClient:
    c = PluggyClient("cid", "secret", base_url="https://api.pluggy.ai")
    c._api_key = "fake"  # pula o POST /auth
    c._http = httpx.Client(base_url=c._base_url, transport=httpx.MockTransport(handler))
    return c


def test_cursor_segue_next_query_relativo():
    paginas: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paginas.append(request.url.path)
        if request.url.path != "/v2/transactions":  # raiz → como o Pluggy real: 403
            return httpx.Response(403, json={"message": "forbidden"})
        if "after" not in request.url.params:
            return httpx.Response(
                200, json={"results": [{"id": "a"}], "next": "?accountId=acc-1&after=CURSOR"}
            )
        return httpx.Response(200, json={"results": [{"id": "b"}], "next": None})

    with _client(handler) as c:
        txs = c.transacoes("acc-1")

    assert [t["id"] for t in txs] == ["a", "b"]
    assert paginas == ["/v2/transactions", "/v2/transactions"]  # nunca a raiz


def test_transacoes_janela_usa_dateFrom_nao_from():
    """Regressão: v2 rejeita `from` (HTTP 400). A janela incremental tem de ir em `dateFrom`."""
    params_vistos: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        params_vistos.update(request.url.params)
        return httpx.Response(200, json={"results": [], "next": None})

    with _client(handler) as c:
        c.transacoes("acc-1", desde=date(2026, 6, 10))

    assert params_vistos.get("dateFrom") == "2026-06-10"
    assert "from" not in params_vistos  # o param que dava 400
