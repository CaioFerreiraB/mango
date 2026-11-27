"""Catálogo curado das principais instituições financeiras BR (para o vínculo manual da conta).

Credenciais sandbox do Pluggy só listam connectors de sandbox — o catálogo real de bancos é
inacessível pela API (fase de descoberta). Então servimos esta lista estática.

Logos: arquivos servidos pela própria origem (`frontend/public/logos/bancos/`), baixados uma vez —
SVG oficial do Pluggy para os connectors verificados, favicon do banco para os demais. Não
apontam para CDN externo: a CSP (`img-src 'self'`) bloquearia, e cada carregamento contaria a
terceiros (Google, Pluggy) quais bancos o usuário tem.
`pluggy_connector_id` é o id real do connector quando conhecido, senão um id sintético estável
(só serve para deduplicar a instituição manual em `upsert_by_connector`).

ponytail: catálogo estático (só os grandes bancos). Em produção (Open Finance real), dá para
mesclar isto com o `GET /connectors` ao vivo do Pluggy — não feito porque o usuário usa sandbox.
"""

from __future__ import annotations


def _logo(connector_id: int, ext: str = "png") -> str:
    return f"/logos/bancos/{connector_id}.{ext}"


# (pluggy_connector_id, nome, logo_url). Os 6 primeiros têm o SVG oficial do Pluggy (verificado).
CATALOGO_BR: list[tuple[int, str, str]] = [
    (212, "Nubank", _logo(212, "svg")),
    (201, "Itaú", _logo(201, "svg")),
    (203, "Bradesco", _logo(203, "svg")),
    (208, "Santander", _logo(208, "svg")),
    (226, "C6 Bank", _logo(226, "svg")),
    (291, "Wise", _logo(291, "svg")),
    (90001, "Banco do Brasil", _logo(90001)),
    (90002, "Caixa Econômica Federal", _logo(90002)),
    (90003, "Banco Inter", _logo(90003)),
    (90004, "PagBank", _logo(90004)),
    (90005, "Mercado Pago", _logo(90005)),
    (90006, "BTG Pactual", _logo(90006)),
    (90007, "Banco Original", _logo(90007)),
    (90008, "Sicoob", _logo(90008)),
    (90009, "Sicredi", _logo(90009)),
    (90010, "Neon", _logo(90010)),
    (90011, "PicPay", _logo(90011)),
    (90012, "Banrisul", _logo(90012)),
    (90013, "Will Bank", _logo(90013)),
    (90014, "Banco Safra", _logo(90014)),
    (90015, "Banco BMG", _logo(90015)),
]
