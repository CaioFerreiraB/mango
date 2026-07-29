"""Cliente HTTP do Pluggy (§4.3). Portado da fase de descoberta (`scripts/discovery`).

Segurança (S1/§5.5):
- `apiKey` vive **só em memória**, na instância (uma por credencial de usuário). Nunca é
  persistida nem devolvida pela API.
- Nada de segredo em log: não instalamos event hooks de logging no httpx; o header
  `X-API-KEY` e o corpo de `/auth` nunca são logados. Erros do Pluggy são redigidos
  (`PluggyError` carrega só método/rota/status, sem corpo) antes de subir.
- `base_url` vem da config (fixo), nunca de input de usuário (evita SSRF, S6). IDs entram
  como query param (httpx faz o URL-encode).
"""

from __future__ import annotations

import time
from datetime import date
from urllib.parse import urljoin

import httpx

from app.config import settings

# Retentativas e limites — o cursor/paginação não pode virar loop infinito (S5).
_MAX_TENTATIVAS = 3
_MAX_BACKOFF_S = 120
_MAX_PAGINAS = 50


class PluggyError(RuntimeError):
    """Falha ao falar com o Pluggy — mensagem já redigida (sem segredo nem corpo cru)."""


class PluggyClient:
    """Um cliente por credencial de usuário. Autentica sob demanda e reusa a `apiKey`."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        *,
        base_url: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._base_url = (base_url or settings.pluggy_base_url).rstrip("/")
        self._api_key: str | None = None
        self._http = httpx.Client(base_url=self._base_url, timeout=timeout)

    def __enter__(self) -> PluggyClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self._http.close()

    def close(self) -> None:
        self._http.close()

    # -- transporte -------------------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json_body: dict | None = None,
        autenticado: bool = True,
    ) -> dict:
        headers = {"X-API-KEY": self._ensure_api_key()} if autenticado else {}
        resp: httpx.Response | None = None
        for _ in range(_MAX_TENTATIVAS):
            try:
                resp = self._http.request(
                    method, path, params=params, json=json_body, headers=headers
                )
            except httpx.HTTPError as e:  # timeout, DNS, conexão — sem vazar detalhe
                raise PluggyError(f"{method} {path}: falha de rede ({type(e).__name__})") from None
            if resp.status_code == 429:
                espera = min(int(resp.headers.get("Retry-After", "60") or "60"), _MAX_BACKOFF_S)
                time.sleep(espera)
                continue
            break
        assert resp is not None
        if resp.status_code >= 400:
            # Sem corpo: pode ecoar dados internos/segredos. Só status + rota.
            raise PluggyError(f"{method} {path} → HTTP {resp.status_code}")
        return resp.json()

    def _ensure_api_key(self) -> str:
        if self._api_key is None:
            self._api_key = self.autenticar()
        return self._api_key

    # -- endpoints --------------------------------------------------------------------

    def autenticar(self) -> str:
        """`POST /auth` → apiKey (~2h). Também serve para validar a credencial ao vivo."""
        data = self._request(
            "POST",
            "/auth",
            json_body={"clientId": self._client_id, "clientSecret": self._client_secret},
            autenticado=False,
        )
        api_key = data.get("apiKey")
        if not api_key:
            raise PluggyError("POST /auth: resposta sem apiKey")
        return api_key

    def item(self, item_id: str) -> dict:
        """`GET /items/{id}` — metadados da conexão (connector, status)."""
        return self._request("GET", f"/items/{item_id}")

    def contas(self, item_id: str) -> list[dict]:
        return self._request("GET", "/accounts", params={"itemId": item_id}).get("results", [])

    def faturas(self, account_id: str) -> list[dict]:
        return self._paginar("/bills", {"accountId": account_id})

    def transacoes(self, account_id: str, *, desde: date | None = None) -> list[dict]:
        """`GET /v2/transactions` (cursor). `desde` limita o delta (janela do sync)."""
        params: dict = {"accountId": account_id}
        if desde is not None:
            # v2 filtra pela data da transação com `dateFrom`. `from`/`to` do v1 dão HTTP 400
            # ("property from should not exist"); `createdAtFrom` filtra por ingestão, não serve.
            params["dateFrom"] = desde.isoformat()
        return self._cursor("/v2/transactions", params)

    def investimentos(self, item_id: str) -> list[dict]:
        """`GET /investments` (page-based) — valores já calculados pelo Pluggy (§4.9, #5)."""
        return self._paginar("/investments", {"itemId": item_id})

    def investimento_transacoes(self, investment_id: str) -> list[dict]:
        """`GET /investments/{id}/transactions` — movimentos/proventos (DY de FII, §4.9)."""
        return self._paginar(f"/investments/{investment_id}/transactions", {})

    def disparar_atualizacao(self, item_id: str) -> dict:
        """`PATCH /items/{id}` — pede ao Pluggy um novo fetch no provedor (limite ~20/min)."""
        return self._request("PATCH", f"/items/{item_id}")

    # -- paginação --------------------------------------------------------------------

    def _paginar(self, path: str, params: dict) -> list[dict]:
        """Paginação por página (`page`/`totalPages`) — usada por /bills."""
        results: list[dict] = []
        page = 1
        while page <= _MAX_PAGINAS:
            body = self._request("GET", path, params={**params, "pageSize": 500, "page": page})
            results.extend(body.get("results", []))
            if page >= body.get("totalPages", 1):
                break
            page += 1
        return results

    def _cursor(self, path: str, params: dict) -> list[dict]:
        """Paginação por cursor (`next`) — /v2/transactions. Cap de páginas evita loop (S5)."""
        results: list[dict] = []
        prox_path: str | None = path
        prox_params: dict | None = params
        for _ in range(_MAX_PAGINAS):
            body = self._request("GET", prox_path, params=prox_params)
            results.extend(body.get("results", []))
            nxt = body.get("next")
            if not nxt:
                break
            # `next` do /v2/transactions é relativo e só-query (?accountId=…&after=…), sem o
            # path. urljoin resolve contra `path` p/ preservar /v2/transactions (senão bate na
            # raiz → 403). Também aceita `next` como URL absoluta ou path-relativo.
            prox_path = urljoin(path, nxt)
            prox_params = None
        return results
