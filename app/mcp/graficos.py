"""Gráficos do MCP (docs/mcp.md §3.4): specs Vega-Lite → PNG (vl-convert) e a MESMA spec no
gráfico interativo do MCP App (`ui/grafico.html`, via vega-embed). Uma fonte de verdade.

Regras da skill dataviz: forma pelo trabalho do dado (magnitude → barras ordenadas; série no
tempo → linhas; composição → barras empilhadas), cores categóricas em ordem fixa da paleta
validada (nunca ciclada; acima de 8 séries dobra em "Outras"), marcas finas com ponta
arredondada, grid em hairline, nunca eixo duplo, legenda a partir de 2 séries. Valores nos
dados em REAIS (o eixo formata com o locale pt-BR).
"""

from pathlib import Path
from typing import Any

import vl_convert as vlc

# Paleta categórica validada (skill dataviz, references/palette.md) — ordem = segurança p/ CVD.
CATEGORICAS = [
    "#2a78d6",
    "#eb6834",
    "#1baf7a",
    "#eda100",
    "#e87ba4",
    "#008300",
    "#6250d6",
    "#e34948",
]
MAX_SERIES = len(CATEGORICAS)

_SUPERFICIE, _TINTA, _TINTA_2, _MUDO, _GRID, _BASE = (
    "#fcfcfb",
    "#0b0b0b",
    "#52514e",
    "#898781",
    "#e1e0d9",
    "#c3c2b7",
)
_FONTE = "system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif"

CONFIG: dict[str, Any] = {
    "background": _SUPERFICIE,
    "font": _FONTE,
    "padding": 16,
    "view": {"stroke": None},
    "title": {"color": _TINTA, "fontSize": 15, "fontWeight": 600, "anchor": "start", "offset": 12},
    "axis": {
        "labelColor": _MUDO,
        "titleColor": _TINTA_2,
        "labelFontSize": 11,
        "titleFontWeight": 500,
        "gridColor": _GRID,
        "gridWidth": 1,
        "domainColor": _BASE,
        "tickColor": _BASE,
        "labelPadding": 6,
    },
    "axisX": {"grid": False},
    "legend": {
        "labelColor": _TINTA_2,
        "titleColor": _TINTA_2,
        "orient": "top",
        "symbolType": "circle",
    },
    "bar": {"cornerRadiusEnd": 4},
    "line": {"strokeWidth": 2},
    "range": {"category": CATEGORICAS},
}

# Locale d3 em pt-BR com espaço depois do R$ (o "pt-BR" embutido dá "R$1.200,00").
LOCALE_NUMERO = {"decimal": ",", "thousands": ".", "grouping": [3], "currency": ["R$ ", ""]}
_MOEDA = "$,.2f"
_MOEDA_EIXO = "$,.0f"
_LARGURA = 640


def _base(titulo: str, dados: list[dict], **resto: Any) -> dict:
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": titulo,
        "width": _LARGURA,
        "data": {"values": dados},
        "config": CONFIG,
        **resto,
    }


def dobrar_em_outras(
    itens: list[tuple[str, float]], maximo: int = MAX_SERIES
) -> list[tuple[str, float]]:
    """Maiores primeiro; da `maximo`-ésima em diante vira "Outras" (nunca gera cor nova)."""
    itens = sorted(itens, key=lambda kv: -kv[1])
    if len(itens) <= maximo:
        return itens
    return [*itens[: maximo - 1], ("Outras", sum(v for _, v in itens[maximo - 1 :]))]


def barras_horizontais(titulo: str, itens: list[tuple[str, float]]) -> dict:
    """Magnitude por categoria: uma só cor (a identidade está no rótulo), ordenada, com o valor
    escrito na ponta da barra."""
    dados = [{"rotulo": r, "valor": v} for r, v in itens]
    y = {"field": "rotulo", "type": "nominal", "sort": "-x", "title": None}
    x = {"field": "valor", "type": "quantitative", "title": None, "axis": {"format": _MOEDA_EIXO}}
    return _base(
        titulo,
        dados,
        height={"step": 28},
        encoding={"y": y, "x": x},
        layer=[
            {
                "mark": {"type": "bar", "color": CATEGORICAS[0], "height": {"band": 0.6}},
                "encoding": {
                    "tooltip": [
                        {"field": "rotulo", "title": "Categoria"},
                        {"field": "valor", "title": "Total", "format": _MOEDA},
                    ]
                },
            },
            {
                "mark": {
                    "type": "text",
                    "align": "left",
                    "dx": 6,
                    "color": _TINTA_2,
                    "fontSize": 11,
                },
                "encoding": {"text": {"field": "valor", "format": _MOEDA}},
            },
        ],
    )


def barras_agrupadas(titulo: str, dados: list[dict]) -> dict:
    """Poucas séries por período (ex.: entradas × saídas por mês): barras lado a lado.
    `dados` = [{periodo, serie, valor}], `periodo` já rotulado e na ordem de exibição."""
    series = list(dict.fromkeys(d["serie"] for d in dados))
    return _base(
        titulo,
        dados,
        height=280,
        mark={"type": "bar", "stroke": _SUPERFICIE, "strokeWidth": 2},
        encoding={
            "x": {
                "field": "periodo",
                "type": "ordinal",
                "sort": None,
                "title": None,
                "axis": {"labelAngle": 0},
                "scale": {"paddingInner": 0.45},
            },
            "xOffset": {"field": "serie", "sort": series, "scale": {"paddingInner": 0.06}},
            "y": {
                "field": "valor",
                "type": "quantitative",
                "title": None,
                "axis": {"format": _MOEDA_EIXO},
            },
            "color": {
                "field": "serie",
                "type": "nominal",
                "sort": series,
                "title": None,
                "scale": {"domain": series, "range": CATEGORICAS[: len(series)]},
            },
            "tooltip": [
                {"field": "periodo", "title": "Período"},
                {"field": "serie", "title": "Série"},
                {"field": "valor", "title": "Valor", "format": _MOEDA},
            ],
        },
    )


def linhas(titulo: str, dados: list[dict]) -> dict:
    """Séries no tempo. `dados` = [{data, serie, valor}]. Crosshair por regra vertical + tooltip
    com todas as séries no ponto (camada de hover da skill)."""
    series = list(dict.fromkeys(d["serie"] for d in dados))[:MAX_SERIES]
    # Chave estável p/ o pivot do tooltip: nome de série vira nome de campo, e "." ou "[" num
    # nome de conta seriam lidos como caminho aninhado pelo Vega-Lite.
    chave = {s: f"s{i}" for i, s in enumerate(series)}
    dados = [{**d, "k": chave[d["serie"]]} for d in dados if d["serie"] in chave]
    cor = {
        "field": "serie",
        "type": "nominal",
        "sort": series,
        "title": None,
        "scale": {"range": CATEGORICAS[: len(series)]},
    }
    if len(series) == 1:
        cor["legend"] = None  # uma série: o título nomeia, sem caixa de legenda
    x = {
        "field": "data",
        "type": "temporal",
        "title": None,
        "axis": {"format": "%d/%m", "tickCount": 6},
    }
    y = {
        "field": "valor",
        "type": "quantitative",
        "title": None,
        "axis": {"format": _MOEDA_EIXO},
        "scale": {"zero": False},
    }
    return _base(
        titulo,
        dados,
        height=280,
        encoding={"x": x},
        layer=[
            {
                "mark": {"type": "line", "interpolate": "monotone"},
                "encoding": {"y": y, "color": cor},
            },
            {
                "params": [
                    {
                        "name": "hover",
                        "select": {
                            "type": "point",
                            "fields": ["data"],
                            "nearest": True,
                            "on": "pointerover",
                            "clear": "pointerout",
                        },
                    }
                ],
                "mark": {"type": "rule", "color": _BASE, "strokeWidth": 1},
                "encoding": {
                    "opacity": {
                        "condition": {"param": "hover", "empty": False, "value": 1},
                        "value": 0,
                    },
                    "tooltip": [
                        {"field": "data", "type": "temporal", "title": "Data", "format": "%d/%m/%Y"}
                    ]
                    + [
                        {"field": chave[s], "type": "quantitative", "title": s, "format": _MOEDA}
                        for s in series
                    ],
                },
                "transform": [{"pivot": "k", "value": "valor", "groupby": ["data"]}],
            },
        ],
    )


def empilhadas(titulo: str, dados: list[dict], series: list[str]) -> dict:
    """Composição por período (ex.: fatura por categoria). `dados` = [{periodo, serie, valor}]
    com `periodo` já como rótulo (dd/mm/aaaa); 2px de superfície entre segmentos."""
    return _base(
        titulo,
        dados,
        height=300,
        mark={
            "type": "bar",
            "stroke": _SUPERFICIE,
            "strokeWidth": 2,
            "cornerRadiusEnd": 0,
            "width": {"band": 0.45},
        },
        encoding={
            "x": {
                "field": "periodo",
                "type": "ordinal",
                "sort": None,
                "title": None,
                "axis": {"labelAngle": 0},
            },
            "y": {
                "field": "valor",
                "type": "quantitative",
                "title": None,
                "stack": "zero",
                "axis": {"format": _MOEDA_EIXO},
            },
            "color": {
                "field": "serie",
                "type": "nominal",
                "sort": series,
                "title": None,
                "scale": {"domain": series, "range": CATEGORICAS[: len(series)]},
            },
            "order": {"field": "ordem"},
            "tooltip": [
                {"field": "periodo", "title": "Fatura"},
                {"field": "serie", "title": "Categoria"},
                {"field": "valor", "title": "Valor", "format": _MOEDA},
            ],
        },
    )


def orcamento(titulo: str, itens: list[dict]) -> dict:
    """Realizado × limite por categoria: barra do realizado e um traço no limite (bullet). Quem
    estourou ganha o rótulo "acima do limite" — status nunca só por cor."""
    dados = [
        {
            **i,
            "maximo": max(i["realizado"], i["limite"]),
            "rotulo_pct": f"{i['percentual']}%"
            + (" · acima do limite" if i["percentual"] > 100 else ""),
        }
        for i in itens
    ]
    y = {"field": "categoria", "type": "nominal", "sort": "-x", "title": None}
    tooltip = [
        {"field": "categoria", "title": "Categoria"},
        {"field": "realizado", "title": "Realizado", "format": _MOEDA},
        {"field": "limite", "title": "Limite", "format": _MOEDA},
        {"field": "rotulo_pct", "title": "Uso"},
    ]
    return _base(
        titulo,
        dados,
        height={"step": 30},
        encoding={"y": y},
        layer=[
            {
                "mark": {"type": "bar", "color": CATEGORICAS[0], "height": {"band": 0.55}},
                "encoding": {
                    "x": {
                        "field": "realizado",
                        "type": "quantitative",
                        "title": None,
                        "axis": {"format": _MOEDA_EIXO},
                    },
                    "tooltip": tooltip,
                },
            },
            {
                "mark": {"type": "tick", "color": _TINTA, "thickness": 2, "bandSize": 22},
                "encoding": {"x": {"field": "limite", "type": "quantitative"}, "tooltip": tooltip},
            },
            {
                "mark": {
                    "type": "text",
                    "align": "left",
                    "dx": 8,
                    "color": _TINTA_2,
                    "fontSize": 11,
                },
                "encoding": {
                    "x": {"field": "maximo", "type": "quantitative"},
                    "text": {"field": "rotulo_pct"},
                },
            },
        ],
    )


def png(spec: dict) -> bytes:
    # allowed_base_urls=[]: a spec nunca busca dados fora (o padrão do vl-convert permite
    # qualquer URL — vetor de SSRF se um dia um campo do usuário chegar a `data.url`).
    return vlc.vegalite_to_png(
        spec, scale=2, format_locale=LOCALE_NUMERO, time_format_locale="pt-BR", allowed_base_urls=[]
    )


HTML_APP = (Path(__file__).parent / "ui" / "grafico.html").read_text(encoding="utf-8")
