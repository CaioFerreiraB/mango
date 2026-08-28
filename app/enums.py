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

# §4.5 categoria — ícone de uma categoria personalizada. Nome do ícone lucide em kebab-case, o
# mesmo que o frontend usa como chave em `lib/api/categoria-icones.ts` (as duas listas precisam
# casar; a de lá é a que de fato desenha). Allowlist na fronteira, e NÃO CHECK no banco: crescer o
# catálogo é rotina de produto e não deve custar uma migration — e um nome fora da lista já
# degradaria sozinho para o ícone padrão no cliente.
ICONE_CATEGORIA = (
    # Os 22 das raízes do Pluggy, para uma categoria própria conversar com a taxonomia.
    "wallet",
    "landmark",
    "trending-up",
    "arrow-left-right",
    "send",
    "scale",
    "wrench",
    "shopping-bag",
    "monitor-smartphone",
    "shopping-cart",
    "utensils-crossed",
    "plane",
    "heart-handshake",
    "dice-5",
    "receipt-text",
    "percent",
    "home",
    "heart-pulse",
    "car",
    "shield-check",
    "gamepad-2",
    "tag",
    # Os que a taxonomia do banco não cobre — o motivo de existir categoria personalizada.
    "paw-print",
    "gift",
    "graduation-cap",
    "baby",
    "dumbbell",
    "coffee",
    "book-open",
    "music",
    "shirt",
    "scissors",
    "hammer",
    "sparkles",
    "briefcase",
    "piggy-bank",
    "cake",
    "church",
    "bus",
    "fuel",
    "wifi",
    "pill",
    "flower-2",
    "camera",
)


def check_in(column: str, values: tuple[str, ...], name: str) -> CheckConstraint:
    """CHECK `column IN (...)` nomeada (entra na naming_convention como ck_<tabela>_<name>)."""
    allowed = ", ".join(repr(v) for v in values)
    return CheckConstraint(f"{column} IN ({allowed})", name=name)
