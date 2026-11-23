"""Schemas do dashboard (§4.10). Valores em centavos; entradas/saídas já excluem
transferências (evita a dupla contagem cartão↔pagamento, §4.2)."""

from datetime import date

from pydantic import BaseModel

from app.schemas.cartao_fatura import FaturaRead
from app.schemas.transacao import TransacaoRead


class GastoCategoria(BaseModel):
    categoria_id: str | None
    total_centavos: int


class DashboardResumo(BaseModel):
    saldo_total_centavos: int
    entradas_centavos: int
    saidas_centavos: int
    resultado_centavos: int  # entradas − saídas (investimento fica fora das duas)
    investido_centavos: int  # aportes − resgates em categoria de investimento; pode ser < 0
    nao_revisadas: int
    gasto_por_categoria: list[GastoCategoria]
    ultimas_transacoes: list[TransacaoRead]
    faturas_abertas: list[FaturaRead]


class SerieBucket(BaseModel):
    """Um período (semana ou mês) da série temporal. `inicio` é a chave; o rótulo é
    formatado no frontend a partir dela e da granularidade."""

    inicio: date
    entradas_centavos: int
    saidas_centavos: int
    resultado_centavos: int
    investido_centavos: int
    por_categoria: list[GastoCategoria]


class DashboardSeries(BaseModel):
    buckets: list[SerieBucket]


class FaturaResumoBucket(BaseModel):
    """Uma fatura do gráfico "últimas faturas" do cartão: total da própria fatura + quebra por
    categoria das compras que caem nela."""

    fatura_id: int
    due_date: date
    total_centavos: int
    por_categoria: list[GastoCategoria]


class FaturasResumo(BaseModel):
    buckets: list[FaturaResumoBucket]


class PatrimonioPonto(BaseModel):
    """Fecho de um mês (o corrente fecha hoje). Contas = só BANK (cartão fica fora)."""

    mes: str  # YYYY-MM
    contas_centavos: int
    investimentos_centavos: int  # bruto
    investimentos_liquido_centavos: int  # bruto − IR − IOF
    total_centavos: int  # contas + investimentos (bruto)
    liquido_centavos: int  # contas + investimentos líquido
    liquido_estimado: bool  # algum snapshot do mês sem líquido gravado → estimado
    tem_investimentos: bool  # False antes do 1º snapshot da carteira (sem dado, não zero)


class PatrimonioSerie(BaseModel):
    pontos: list[PatrimonioPonto]


class CartaoPainel(BaseModel):
    """Um cartão no painel do dashboard. Compras = DEBIT do cartão (sem transferência), em grandeza;
    fatura atual = saldo da conta CREDIT (o que o Pluggy dá como fatura em aberto); próximas =
    lançamentos com data futura (parcelas e compras ainda não faturadas)."""

    conta_id: int
    nome: str
    fecha: date | None
    vence: date | None
    limite_centavos: int | None
    disponivel_centavos: int | None
    compras_mes_centavos: int
    fatura_atual_centavos: int
    proximas_centavos: int


class CartoesResumo(BaseModel):
    compras_mes_centavos: int
    fatura_atual_centavos: int
    proximas_centavos: int
    total_ano_centavos: int
    media_mes_centavos: int  # total do ano ÷ meses decorridos (o corrente conta)
    cartoes: list[CartaoPainel]


class ContraparteTotal(BaseModel):
    """Estabelecimento/destinatário (despesa) ou pagador (receita), como o banco nomeia.
    `chave` = nome normalizado (filtro do drill-down)."""

    chave: str
    nome: str
    total_centavos: int
    quantidade: int


class ContaTotal(BaseModel):
    conta_id: int
    nome: str
    total_centavos: int


class MeioTotal(BaseModel):
    meio: str  # "Pix", "Cartão de crédito", "Boleto"… (ver `gasto_usuario.meio_de`)
    total_centavos: int
    por_conta: list[ContaTotal]  # vazio para lançamentos de divisão (sem conta)


class DiaSemanaTotal(BaseModel):
    dia: int  # 0 = segunda … 6 = domingo
    total_centavos: int
    ocorrencias: int  # quantos desses dias o período tem (até hoje), com ou sem movimento


class AcumuladoPonto(BaseModel):
    """Dia `indice` (0 = 1º dia) do período atual e do anterior equivalente, lado a lado."""

    indice: int
    data: date
    atual_centavos: int | None  # None depois de hoje
    anterior_centavos: int | None  # None além do tamanho do período anterior
    esperado_centavos: int | None  # ritmo do orçamento (pró-rata diário); None sem orçamento


class PrevistoMes(BaseModel):
    mes: str  # YYYY-MM (mês inteiro)
    previsto_centavos: int | None  # soma dos orçamentos do tipo no mês; None = sem orçamento
    realizado_centavos: int


class AnaliseNatureza(BaseModel):
    """Aba Receitas ou Despesas do dashboard: mesmas regras dos KPIs (sem transferências nem
    investimento; estorno de cartão abate despesa; parte do usuário nas divisões)."""

    natureza: str  # receita | despesa
    anterior_inicio: date
    anterior_fim: date
    total_centavos: int
    anterior_centavos: int
    quantidade: int
    por_categoria: list[GastoCategoria]
    contrapartes: list[ContraparteTotal]  # as 5 maiores
    outras_contrapartes_centavos: int
    outras_contrapartes_quantidade: int  # quantas contrapartes caem em "Outros"
    meios: list[MeioTotal]
    dias_semana: list[DiaSemanaTotal]
    acumulado: list[AcumuladoPonto]
    previsto: list[PrevistoMes]  # meses inteiros que o período toca
