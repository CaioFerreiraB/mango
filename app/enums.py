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

# §4.11 divisao_despesa — "quem pagou" é campo próprio (pago_por_usuario_id); aqui só "como
# divide": entre N participantes (incl. quem pagou) ou o valor cheio p/ 1 único devedor.
MODO_DIVISAO = ("igualmente", "integral")

# §4.6 orcamento — tipo do orçamento (categoria não carrega tipo, o orçamento sim)
TIPO_ORCAMENTO = ("despesa", "receita")

# §4.5 regra_categorizacao — como o texto da regra casa o nome da transação:
# "exato" = nome normalizado idêntico; "contem" = texto da regra é substring do nome.
TIPO_MATCH = ("exato", "contem")

# §5.2 usuario — tipo de conta: acesso completo ou só ao módulo de divisão de contas.
TIPO_USUARIO = ("completo", "divisao")


def check_in(column: str, values: tuple[str, ...], name: str) -> CheckConstraint:
    """CHECK `column IN (...)` nomeada (entra na naming_convention como ck_<tabela>_<name>)."""
    allowed = ", ".join(repr(v) for v in values)
    return CheckConstraint(f"{column} IN ({allowed})", name=name)
