"""Catálogo curado das principais instituições financeiras BR (para o vínculo manual da conta).

Credenciais sandbox do Pluggy só listam connectors de sandbox — o catálogo real de bancos é
inacessível pela API (fase de descoberta). Então servimos esta lista estática.

Logos: SVG oficial do Pluggy (`cdn.pluggy.ai/assets/connector-icons/{id}.svg`) para os connectors
que verificamos; para os demais, o favicon do próprio banco (sempre o logo certo, ainda que menor).
`pluggy_connector_id` é o id real do connector quando conhecido, senão um id sintético estável
(só serve para deduplicar a instituição manual em `upsert_by_connector`).

ponytail: catálogo estático (só os grandes bancos). Em produção (Open Finance real), dá para
mesclar isto com o `GET /connectors` ao vivo do Pluggy — não feito porque o usuário usa sandbox.
"""

from __future__ import annotations


def _pluggy(connector_icon_id: int) -> str:
    return f"https://cdn.pluggy.ai/assets/connector-icons/{connector_icon_id}.svg"


def _favicon(dominio: str) -> str:
    return f"https://www.google.com/s2/favicons?domain={dominio}&sz=128"


# (pluggy_connector_id, nome, logo_url). Os 6 primeiros têm o logo oficial do Pluggy (verificado).
CATALOGO_BR: list[tuple[int, str, str]] = [
    (212, "Nubank", _pluggy(212)),
    (201, "Itaú", _pluggy(201)),
    (203, "Bradesco", _pluggy(203)),
    (208, "Santander", _pluggy(208)),
    (226, "C6 Bank", _pluggy(226)),
    (291, "Wise", _pluggy(291)),
    (90001, "Banco do Brasil", _favicon("bb.com.br")),
    (90002, "Caixa Econômica Federal", _favicon("caixa.gov.br")),
    (90003, "Banco Inter", _favicon("bancointer.com.br")),
    (90004, "PagBank", _favicon("pagbank.com.br")),
    (90005, "Mercado Pago", _favicon("mercadopago.com.br")),
    (90006, "BTG Pactual", _favicon("btgpactual.com")),
    (90007, "Banco Original", _favicon("original.com.br")),
    (90008, "Sicoob", _favicon("sicoob.com.br")),
    (90009, "Sicredi", _favicon("sicredi.com.br")),
    (90010, "Neon", _favicon("neon.com.br")),
    (90011, "PicPay", _favicon("picpay.com")),
    (90012, "Banrisul", _favicon("banrisul.com.br")),
    (90013, "Will Bank", _favicon("willbank.com.br")),
    (90014, "Banco Safra", _favicon("safra.com.br")),
    (90015, "Banco BMG", _favicon("bancobmg.com.br")),
]
