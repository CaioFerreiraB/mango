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
    resultado_centavos: int
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
