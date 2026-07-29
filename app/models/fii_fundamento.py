"""Fundamentos de FII por fundo — dados abertos da CVM (Informe Mensal/Trimestral).

Referência **global** (compartilhada entre usuários, como `categoria`) → SEM `UserOwnedMixin`.
A ponte é o `isin`: `investimento.isin` (Pluggy) → `Codigo_ISIN` (CVM) → CNPJ e fundamentos.
Preço/proventos NÃO moram aqui (seguem de brapi/Pluggy). Ingestão em `app/services/cvm_fii.py`.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import BigInteger, Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin


class FiiFundamento(TimestampMixin, Base):
    __tablename__ = "fii_fundamento"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Chave da ponte com o Pluggy — normalizado em maiúsculas. Um fundo por ISIN.
    isin: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, index=True)
    cnpj: Mapped[str] = mapped_column(String(20), nullable=False)
    nome: Mapped[str | None] = mapped_column(String(255))

    administrador_nome: Mapped[str | None] = mapped_column(String(255))
    administrador_cnpj: Mapped[str | None] = mapped_column(String(20))
    data_funcionamento: Mapped[date | None] = mapped_column(Date)
    segmento: Mapped[str | None] = mapped_column(String(64))
    mandato: Mapped[str | None] = mapped_column(String(64))
    tipo_gestao: Mapped[str | None] = mapped_column(String(32))
    # Derivado (tijolo | papel | hibrido | fof) de mandato + segmento + gestão.
    tipo: Mapped[str | None] = mapped_column(String(16))

    patrimonio_liquido_centavos: Mapped[int | None] = mapped_column(BigInteger)
    num_cotistas: Mapped[int | None] = mapped_column(Integer)
    valor_patrimonial_cota_centavos: Mapped[int | None] = mapped_column(BigInteger)
    dividend_yield_12m_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))

    # Informe Trimestral (só fundos de tijolo têm imóvel; agregado por fundo).
    vacancia_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    inadimplencia_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))

    data_referencia: Mapped[date] = mapped_column(Date, nullable=False)  # competência do mensal
    data_referencia_trimestral: Mapped[date | None] = mapped_column(Date)

    alocacao: Mapped[list["FiiFundamentoAlocacao"]] = relationship(
        back_populates="fundamento", cascade="all, delete-orphan"
    )


class FiiFundamentoAlocacao(Base):
    """Composição da carteira do fundo (Informe Mensal `ativo_passivo`), % do total investido."""

    __tablename__ = "fii_fundamento_alocacao"

    id: Mapped[int] = mapped_column(primary_key=True)
    fundamento_id: Mapped[int] = mapped_column(
        ForeignKey("fii_fundamento.id", ondelete="CASCADE"), nullable=False, index=True
    )
    classe: Mapped[str] = mapped_column(String(64), nullable=False)  # CRI, Imóveis, Caixa, FIIs…
    valor_centavos: Mapped[int] = mapped_column(BigInteger, nullable=False)
    pct: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)

    fundamento: Mapped["FiiFundamento"] = relationship(back_populates="alocacao")
