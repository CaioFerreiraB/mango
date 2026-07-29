"""Valores permitidos de enums de domínio (string + CHECK; portável SQLite/Postgres).

Fonte única dos valores usados nas CHECK constraints dos models. Os schemas Pydantic
declaram os mesmos valores como `Literal` (validação na fronteira + OpenAPI).
"""

from sqlalchemy import CheckConstraint

# §4.1 fonte_de_renda
TIPO_FONTE = ("fixa", "variavel")
RECORRENCIA = ("mensal", "trimestral", "semestral", "anual", "irregular")

# §4.2 conta
CONTA_TYPE = ("BANK", "CREDIT")
CONTA_SUBTYPE = ("CHECKING_ACCOUNT", "SAVINGS_ACCOUNT", "CREDIT_CARD")

# §4.3–4.5 transacao
TRANSACAO_TYPE = ("DEBIT", "CREDIT")
TRANSACAO_STATUS = ("POSTED", "PENDING")
TRANSFERENCIA_ORIGEM = ("auto", "manual")

# §4.7 assinatura — periodicidade (mesma família da recorrência)
PERIODICIDADE = ("mensal", "trimestral", "semestral", "anual", "irregular")

# §4.11 divisao_despesa
MODO_DIVISAO = (
    "pago_mim_dividir",
    "pago_mim_recebo",
    "pago_outro_dividir",
    "pago_outro_recebo",
)


def check_in(column: str, values: tuple[str, ...], name: str) -> CheckConstraint:
    """CHECK `column IN (...)` nomeada (entra na naming_convention como ck_<tabela>_<name>)."""
    allowed = ", ".join(repr(v) for v in values)
    return CheckConstraint(f"{column} IN ({allowed})", name=name)
