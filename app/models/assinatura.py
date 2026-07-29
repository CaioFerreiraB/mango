"""Assinaturas (§4.7). CRUD do usuário (manual) ou criada pela autodetecção do sync."""

from datetime import date

from sqlalchemy import JSON, BigInteger, Boolean, Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.enums import PERIODICIDADE, check_in
from app.models.mixins import TimestampMixin, UserOwnedMixin


class Assinatura(UserOwnedMixin, TimestampMixin, Base):
    __tablename__ = "assinatura"
    __table_args__ = (check_in("periodicidade", PERIODICIDADE, "periodicidade"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text)
    # Nomes de transação (aliases) que casam esta assinatura no sync/dedup, independentes do rótulo
    # `nome` (§4.7). ponytail: JSON em vez de tabela filha — escala pessoal, match/dedup em Python;
    # teto: sem índice/uniq, promover a tabela se algum dia precisar de query por alias no banco.
    nomes_transacao: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    valor_centavos: Mapped[int] = mapped_column(BigInteger, nullable=False)
    categoria_id: Mapped[str | None] = mapped_column(
        ForeignKey("categoria.pluggy_id", ondelete="SET NULL"), index=True
    )
    periodicidade: Mapped[str] = mapped_column(String(16), nullable=False)
    data_inicio: Mapped[date | None] = mapped_column(Date)
    ativa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    detectada_automaticamente: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    conta_id: Mapped[int | None] = mapped_column(
        ForeignKey("conta.id", ondelete="SET NULL"), index=True
    )
