"""Erros de domínio. Serviços os levantam; um handler no `main` os traduz p/ HTTP.

Mantém regra de negócio fora das rotas (§5.2) e desacopla serviços do FastAPI.
"""


class DomainError(Exception):
    """Erro de domínio com mensagem amigável."""

    def __init__(self, mensagem: str) -> None:
        super().__init__(mensagem)
        self.mensagem = mensagem


class NotFoundError(DomainError):
    """Recurso inexistente ou de outro usuário (→ 404)."""


class ConflictError(DomainError):
    """Violação de unicidade/estado (→ 409)."""


class ValidationError(DomainError):
    """Regra de negócio violada (→ 422)."""


class RateLimitError(DomainError):
    """Ação repetida cedo demais — throttle do sync (→ 429)."""


class UpstreamError(DomainError):
    """Falha numa dependência externa, ex.: Pluggy (→ 502). Mensagem genérica ao cliente."""
