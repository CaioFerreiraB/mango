"""Cabecalhos de seguranca (F-2): CSP, nosniff, frame-options e HSTS, por rota."""

from fastapi.testclient import TestClient


def test_resposta_comum_tem_cabecalhos_estritos(sh_client: TestClient) -> None:
    r = sh_client.get("/health")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    # self_hosted fica atras do Caddy (TLS) → HSTS presente.
    assert "max-age=" in r.headers["Strict-Transport-Security"]
    csp = r.headers["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in csp
    assert "script-src 'self'" in csp
    assert "telegram.org" not in csp


def test_miniapp_telegram_afrouxa_csp_e_omite_frame_options(sh_client: TestClient) -> None:
    # Mesmo sem o build do SPA (404 no CI), o middleware roda e decide a CSP pela rota.
    r = sh_client.get("/telegram/revisao")
    csp = r.headers["Content-Security-Policy"]
    assert "script-src 'self' https://telegram.org" in csp
    assert "frame-ancestors https://web.telegram.org https://telegram.org" in csp
    # a allowlist de moldura vive no CSP; X-Frame-Options nao sabe express-la → ausente.
    assert "X-Frame-Options" not in r.headers


def test_docs_fica_sem_csp(sh_client: TestClient) -> None:
    r = sh_client.get("/docs")
    assert r.status_code == 200
    assert "Content-Security-Policy" not in r.headers
    # os cabecalhos baratos seguem presentes.
    assert r.headers["X-Content-Type-Options"] == "nosniff"
