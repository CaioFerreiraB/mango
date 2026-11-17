"""Cabecalhos de seguranca na resposta (F-2): defesa contra clickjacking, MIME-sniffing e
downgrade de transporte. Complementa o CSRF (app.security.csrf) e o SameSite dos cookies.

A CSP e o ponto delicado num SPA: duas rotas fogem do default estrito.
  - /docs, /redoc e /openapi.json (Swagger/ReDoc) carregam JS de CDN e tem script inline — uma
    CSP estrita quebraria a UI. Ficam sem CSP (sao infra interna do dono, nao superficie publica).
  - /telegram/* e o mini app: roda DENTRO do Telegram (iframe no Telegram Web) e injeta o SDK de
    https://telegram.org (ver frontend/src/lib/telegram.ts). Por isso essas rotas liberam
    telegram.org no script-src, trocam o frame-ancestors 'none' por uma allowlist do Telegram e
    NAO mandam X-Frame-Options (que nao sabe expressar allowlist). O resto do app segue trancado:
    script so da origem, sem moldura.

HSTS so no modo self_hosted: e la que o app fica atras do Caddy com TLS. No desktop (localhost
http) o navegador ignoraria o header, mas gatear deixa a intencao explicita.
"""

from collections.abc import Awaitable, Callable

from fastapi import Request, Response

from app.config import settings

# Infra que serve a propria UI com inline/CDN — fica fora da CSP (nunca e superficie de usuario).
_SEM_CSP = ("/docs", "/redoc", "/openapi.json")

# 'unsafe-inline' so no style-src: o Tailwind v4 injeta uma tag <style> em runtime. O script
# continua trancado em 'self' (o build do Vite referencia so o modulo com hash, sem inline).
_PARTES_COMUNS = (
    "default-src 'self'",
    "base-uri 'self'",
    "object-src 'none'",
    "form-action 'self'",
    "img-src 'self' data: blob:",
    "font-src 'self' data:",
    "style-src 'self' 'unsafe-inline'",
    "worker-src 'self' blob:",
    "connect-src 'self'",
    "manifest-src 'self'",
)

_CSP_ESTRITA = "; ".join((*_PARTES_COMUNS, "frame-ancestors 'none'", "script-src 'self'"))

# Mini app do Telegram: precisa carregar o SDK de telegram.org e ser embutido pelo Telegram Web.
_CSP_MINIAPP = "; ".join(
    (
        *_PARTES_COMUNS,
        "frame-ancestors https://web.telegram.org https://telegram.org",
        "script-src 'self' https://telegram.org",
    )
)


async def security_headers_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    response = await call_next(request)
    headers = response.headers
    path = request.url.path

    headers.setdefault("X-Content-Type-Options", "nosniff")
    headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    if settings.app_mode == "self_hosted":
        # Atras do Caddy (TLS): 2 anos, subdominios e elegivel a preload.
        headers.setdefault(
            "Strict-Transport-Security", "max-age=63072000; includeSubDomains; preload"
        )

    if path.startswith("/telegram"):
        # Sem X-Frame-Options: ele nao expressa allowlist; quem autoriza a moldura e o CSP.
        headers["Content-Security-Policy"] = _CSP_MINIAPP
        return response

    if path.startswith(_SEM_CSP):
        return response

    headers.setdefault("X-Frame-Options", "DENY")
    headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    headers["Content-Security-Policy"] = _CSP_ESTRITA
    return response
