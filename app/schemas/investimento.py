"""Schemas de `investimento` (Pluggy-owned): leitura + update estreito (objetivo_id) +
agregados server-side da carteira (§4.9) — o frontend só exibe."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.investimento import Investimento, InvestimentoTransacao
from app.schemas.auto import read_model

InvestimentoRead = read_model(Investimento)
InvestimentoTransacaoRead = read_model(InvestimentoTransacao)


class InvestimentoUpdate(BaseModel):
    objetivo_id: int | None = None
    # Vincular esta compra (posição) a um ativo do usuário (§4.9). None desvincula.
    ativo_id: int | None = None


class AporteManualCreate(BaseModel):
    """Aporte (compra) informado à mão, quando o banco não traz o histórico completo (§4.9)."""

    data: date
    quantidade: Decimal = Field(gt=0)
    valor_centavos: int = Field(ge=0)  # total pago no aporte


class AporteManualUpdate(BaseModel):
    data: date | None = None
    quantidade: Decimal | None = Field(default=None, gt=0)
    valor_centavos: int | None = Field(default=None, ge=0)


# --- resumo da carteira ---------------------------------------------------------------


class CarteiraTotais(BaseModel):
    valor_centavos: int
    liquido_centavos: int  # valor de resgate (bruto menos IR/IOF do Pluggy)
    investido_centavos: int | None
    resultado_centavos: int | None
    resultado_pct: float | None
    quantidade_ativos: int


class CarteiraAlocacao(BaseModel):
    tipo: str  # subtype (fallback type) do Pluggy: CDB, REAL_ESTATE_FUND, ETF…
    valor_centavos: int
    pct: float


class CarteiraAtivoRV(BaseModel):
    """Renda variável agrupada por ativo (spec §4.9: total investido, bruto e valorização)."""

    code: str
    nome: str | None
    investimento_ids: list[int]
    quantidade: float | None
    preco_medio_centavos: int | None
    investido_centavos: int | None
    valor_centavos: int
    valorizacao_centavos: int | None
    valorizacao_pct: float | None


class CarteiraItem(BaseModel):
    id: int
    nome: str | None
    type: str
    subtype: str | None
    code: str | None
    valor_centavos: int
    investido_centavos: int | None
    resultado_centavos: int | None
    resultado_pct: float | None
    annual_rate: float | None
    last_twelve_months_rate: float | None
    due_date: datetime | None
    objetivo_id: int | None


class CarteiraGrupo(BaseModel):
    type: str  # EQUITY | ETF | FIXED_INCOME | MUTUAL_FUND | SECURITY | …
    valor_centavos: int
    itens: list[CarteiraItem]


class CarteiraAtivoRF(BaseModel):
    """Renda fixa agrupada por ativo do usuário (§4.9): resultado = soma das compras/posições."""

    ativo_id: int | None  # None = posição avulsa (ainda sem ativo)
    nome: str | None
    investimento_ids: list[int]
    investido_centavos: int | None
    valor_centavos: int
    resultado_centavos: int | None
    resultado_pct: float | None
    posicoes: list[CarteiraItem]  # as compras, p/ expandir


class CarteiraPosicao(BaseModel):
    """Uma linha da tabela da Carteira: o ativo já agrupado (RV por código, RF por `ativo`,
    resto por posição), com tudo que a tela mostra. Frontend só exibe."""

    chave: str  # id estável de linha: rv-{code} | rf-{ativo_id} | rf-avulsa-{id} | pos-{id}
    nome: str | None
    code: str | None
    type: str
    subtype: str | None
    instituicao: str | None  # efetiva: vínculo manual, senão connector; fallback emissor
    instituicao_logo_url: str | None = None  # só quando vinculada à mão (connector não traz logo)
    quantidade: float | None
    preco_medio_centavos: int | None
    cotacao_centavos: int | None  # preço unitário (value_unitario) em centavos
    investido_centavos: int | None
    valor_centavos: int
    resultado_centavos: int | None
    resultado_pct: float | None
    participacao_pct: float | None  # % do valor da carteira
    investimento_ids: list[int]
    # Histórico incompleto: RV sem custo do Pluggy cujos movimentos não cobrem a posição atual
    # (há compras fora da janela de 12 meses) → preço médio/investido saem parciais; o usuário
    # completa com aportes manuais. `False` quando o custo cobre toda a posição.
    historico_incompleto: bool = False


class CarteiraResumo(BaseModel):
    totais: CarteiraTotais
    alocacao: list[CarteiraAlocacao]
    renda_variavel: list[CarteiraAtivoRV]
    renda_fixa: list[CarteiraAtivoRF]
    grupos: list[CarteiraGrupo]
    posicoes: list[CarteiraPosicao]  # tabela plana (novo design da Carteira)


# --- proventos / série ----------------------------------------------------------------


class ProventosFII(BaseModel):
    investimento_id: int
    inicio: date
    fim: date
    total_centavos: int
    total_isento_centavos: int  # rendimentos de FII (INTEREST/DIVIDEND) são isentos de IR
    dy_pct: float | None
    proventos: list[InvestimentoTransacaoRead]  # type: ignore[valid-type]


class FundamentosFIIAlocacao(BaseModel):
    classe: str
    valor_centavos: int
    pct: float


class FundamentosFII(BaseModel):
    """Fundamentos do FII (CVM) para uma posição, + P/VP calculado. `disponivel=False` quando não é
    FII ou a ingestão ainda não trouxe o fundo. Todos os campos nullable (dado externo/parcial)."""

    disponivel: bool
    isin: str | None = None
    cnpj: str | None = None
    nome: str | None = None
    administrador_nome: str | None = None
    administrador_cnpj: str | None = None
    data_funcionamento: date | None = None
    segmento: str | None = None
    mandato: str | None = None
    tipo_gestao: str | None = None
    tipo: str | None = None
    patrimonio_liquido_centavos: int | None = None
    num_cotistas: int | None = None
    valor_patrimonial_cota_centavos: int | None = None
    dividend_yield_12m_pct: float | None = None
    vacancia_pct: float | None = None
    inadimplencia_pct: float | None = None
    pvp: float | None = None  # cotação (Pluggy) ÷ valor patrimonial da cota
    cotacao_centavos: int | None = None
    data_referencia: date | None = None
    data_referencia_trimestral: date | None = None
    atualizado_em: datetime | None = None
    alocacao: list[FundamentosFIIAlocacao] = []


class CotaSeriePonto(BaseModel):
    data: date
    valor_centavos: int  # preço de fechamento da cota (brapi) em centavos


class CarteiraSeriePonto(BaseModel):
    data: date
    valor_centavos: int
    investido_centavos: int  # capital aportado acumulado no dia (linha "Investido" do gráfico)
    acumulado_pct: float


class CarteiraSerie(BaseModel):
    recorte: str
    subtype: str | None
    pontos: list[CarteiraSeriePonto]
    # Renda fixa sem cotação histórica: pontos até esta data foram estimados (capitalização dos
    # aportes pelo indexador realizado), não medidos. `None` quando nada foi reconstruído.
    reconstruido_ate: date | None = None


# --- visão geral (dashboard do módulo) ------------------------------------------------


class VisaoGeralInvestimentos(BaseModel):
    rentabilidade_12m_pct: float | None  # TWR dos últimos 12 meses (janela disponível)
    vs_cdi_pp: float | None  # p.p. acima/abaixo do CDI no mesmo período
    dividendos_mes_centavos: int  # proventos recebidos no mês corrente
