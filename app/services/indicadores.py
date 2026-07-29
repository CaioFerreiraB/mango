"""Indicadores de mercado (§4.9/§5.6) — séries normalizadas p/ comparação com a carteira.

Fontes:
- **BCB SGS** (sem chave): CDI (12, % a.d.), SELIC (11, % a.d.), IPCA (433, % a.m.).
- **brapi.dev** (token opcional em `settings.brapi_token`): IBOV (^BVSP) e preços históricos
  de tickers (reconstrução da renda variável na série da carteira).

Toda série sai como pontos (dia civil SP, % acumulado desde o início do período), com
forward-fill de dias sem observação — pronto p/ plotar contra a série da carteira.

Segurança: URLs fixas por config (nunca de input do usuário, SSRF); erros redigidos —
`IndicadorError` carrega só rota/status, nunca corpo nem token.

`ponytail:` cache in-memory com TTL (dict de módulo) — refetch é barato e o dado muda no
máximo 1×/dia; se precisar sobreviver a restart, promover p/ tabela.
"""

from __future__ import annotations

import time as time_mod
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

import httpx

from app.config import settings
from app.services.periodo import SP

_TTL_S = 12 * 3600
_cache: dict[tuple, tuple[float, object]] = {}
_transport: httpx.BaseTransport | None = None  # p/ testes (MockTransport)

_SGS_BASE = "https://api.bcb.gov.br/dados/serie"
# codigo → (série SGS, periodicidade do %)
_SGS = {"cdi": (12, "diaria"), "selic": (11, "diaria"), "ipca": (433, "mensal")}
_NOMES = {"cdi": "CDI", "selic": "SELIC", "ipca": "IPCA", "ibov": "IBOV"}


class IndicadorError(RuntimeError):
    """Falha ao buscar dado de mercado — mensagem já redigida (sem corpo/token)."""

    def __init__(self, msg: str, status: int | None = None):
        super().__init__(msg)
        self.status = status


def disponiveis(token: str | None = None) -> list[dict]:
    """Indicadores oferecidos ao usuário (§4.9: "dentro da lista disponível"). IBOV depende do
    token brapi (do perfil ou do ambiente)."""
    token = token if token is not None else settings.brapi_token
    out = [{"codigo": c, "nome": _NOMES[c]} for c in _SGS]
    if token:
        out.append({"codigo": "ibov", "nome": _NOMES["ibov"]})
    return out


def serie(
    codigo: str, inicio: date, fim: date, token: str | None = None
) -> list[tuple[date, float]]:
    """Pontos (dia civil, % acumulado desde `inicio`) do indicador, forward-fill."""
    if codigo in _SGS:
        sgs_codigo, periodicidade = _SGS[codigo]
        bruto = _sgs_serie(sgs_codigo, inicio, fim)
        # Fator composto aplicado na data da observação (dia útil p/ CDI/SELIC; 1º do mês
        # p/ IPCA — o índice do mês entra como degrau, mesmo publicado com defasagem).
        acumulado: dict[date, Decimal] = {}
        fator = Decimal(1)
        for d, v in sorted(bruto):
            fator *= 1 + v / 100
            acumulado[d] = (fator - 1) * 100
        return _forward_fill(acumulado, inicio, fim)
    if codigo == "ibov":
        closes = precos_historicos("^BVSP", inicio, fim, token)
        if not closes:
            return []
        base = closes[min(closes)]
        pct = {d: (v / base - 1) * 100 for d, v in closes.items()}
        return _forward_fill(pct, inicio, fim)
    raise IndicadorError(f"indicador desconhecido: {codigo}")


def precos_historicos(
    ticker: str, inicio: date, fim: date, token: str | None = None
) -> dict[date, Decimal]:
    """Fechamentos diários do ticker via brapi (exige token — do perfil ou do ambiente). dict dia
    civil SP → close."""
    token = token if token is not None else settings.brapi_token
    if not token:
        raise IndicadorError("brapi_token não configurado")

    def fetch() -> dict[date, Decimal]:
        body = _get_json(
            f"{settings.brapi_base_url}/quote/{ticker}",
            {
                "range": _range_brapi(inicio),
                "interval": "1d",
                "token": token,
            },
        )
        resultados = body.get("results") or [{}]
        out: dict[date, Decimal] = {}
        for row in resultados[0].get("historicalDataPrice") or []:
            ts, close = row.get("date"), row.get("close")
            if ts is None or close is None:
                continue
            try:
                d = datetime.fromtimestamp(ts, tz=SP).date()
                out[d] = Decimal(str(close))
            except (ValueError, OSError, InvalidOperation):
                continue
        return {d: v for d, v in out.items() if inicio <= d <= fim}

    return _cached(("brapi", ticker, inicio, fim), fetch)


# --- fontes ---------------------------------------------------------------------------


def _sgs_serie(sgs_codigo: int, inicio: date, fim: date) -> list[tuple[date, Decimal]]:
    def fetch() -> list[tuple[date, Decimal]]:
        try:
            body = _get_json(
                f"{_SGS_BASE}/bcdata.sgs.{sgs_codigo}/dados",
                {
                    "formato": "json",
                    "dataInicial": inicio.strftime("%d/%m/%Y"),
                    "dataFinal": fim.strftime("%d/%m/%Y"),
                },
            )
        except IndicadorError as e:
            if e.status == 404:
                return []  # SGS responde 404 p/ intervalo sem observação (ex.: IPCA mensal em janela curta)
            raise
        out: list[tuple[date, Decimal]] = []
        for row in body if isinstance(body, list) else []:
            try:
                out.append(
                    (
                        datetime.strptime(row["data"], "%d/%m/%Y").date(),
                        Decimal(str(row["valor"])),
                    )
                )
            except (KeyError, ValueError, InvalidOperation):
                continue  # linha malformada não derruba a série
        return out

    return _cached(("sgs", sgs_codigo, inicio, fim), fetch)


def _get_json(url: str, params: dict) -> dict | list:
    try:
        with httpx.Client(transport=_transport, timeout=30.0) as http:
            resp = http.get(url, params=params)
    except httpx.HTTPError as e:  # sem vazar detalhe (params carregam o token do brapi)
        raise IndicadorError(f"GET {url}: falha de rede ({type(e).__name__})") from None
    if resp.status_code >= 400:
        raise IndicadorError(f"GET {url} → HTTP {resp.status_code}", status=resp.status_code)
    return resp.json()


# --- helpers --------------------------------------------------------------------------


def _cached(key: tuple, fetch):
    agora = time_mod.monotonic()
    hit = _cache.get(key)
    if hit is not None and agora - hit[0] < _TTL_S:
        return hit[1]
    dado = fetch()
    _cache[key] = (agora, dado)
    return dado


def _forward_fill(pontos: dict[date, Decimal], inicio: date, fim: date) -> list[tuple[date, float]]:
    """Um ponto por dia civil em [inicio, fim]; dias sem observação repetem o anterior
    (fins de semana/feriados); antes da 1ª observação, 0%."""
    out: list[tuple[date, float]] = []
    atual = Decimal(0)
    d = inicio
    while d <= fim:
        atual = pontos.get(d, atual)
        out.append((d, float(atual)))
        d += timedelta(days=1)
    return out


def _range_brapi(inicio: date) -> str:
    """Menor `range` do brapi que cobre desde `inicio` (a API só aceita presets)."""
    dias = (date.today() - inicio).days
    for range_, cobertura in (
        ("1mo", 28),
        ("3mo", 88),
        ("6mo", 178),
        ("1y", 360),
        ("2y", 725),
        ("5y", 1820),
    ):
        if dias <= cobertura:
            return range_
    return "max"
