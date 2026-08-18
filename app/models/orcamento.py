"""Orçamentos por categoria (§4.6, decisão #20). CRUD do usuário.

Regra #20 (soma das subcategorias ≤ categoria) é validada no service `orcamento`, sempre
escopada por `tipo` — uma árvore de despesa e uma de receita são orçadas independentemente.
`orcamento_mensal` é materializado de `orcamento` e editável por mês (base dos alertas).
"""

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.enums import TIPO_ORCAMENTO, check_in
from app.models.mixins import TimestampMixin, UserOwnedMixin


class Orcamento(UserOwnedMixin, TimestampMixin, Base):
    __tablename__ = "orcamento"
    __table_args__ = (
        UniqueConstraint("usuario_id", "categoria_id", "tipo"),
        check_in("tipo", TIPO_ORCAMENTO, "tipo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    categoria_id: Mapped[str] = mapped_column(
        ForeignKey("categoria.pluggy_id", ondelete="RESTRICT"), nullable=False, index=True
    )
    tipo: Mapped[str] = mapped_column(String(16), nullable=False)  # despesa | receita
    limite_padrao_centavos: Mapped[int] = mapped_column(BigInteger, nullable=False)
    recorrente: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Ordem de exibição dentro do tipo (arrastar-para-reordenar no modal padrão) — sempre
    # atribuída pelo servidor (nunca aceita do cliente na criação, só editável via PATCH).
    ordem: Mapped[int] = mapped_column(Integer, nullable=False)


class OrcamentoMensal(UserOwnedMixin, TimestampMixin, Base):
    __tablename__ = "orcamento_mensal"
    __table_args__ = (
        UniqueConstraint("usuario_id", "categoria_id", "ano", "mes", "tipo"),
        check_in("tipo", TIPO_ORCAMENTO, "tipo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    orcamento_id: Mapped[int] = mapped_column(
        ForeignKey("orcamento.id", ondelete="CASCADE"), nullable=False, index=True
    )
    categoria_id: Mapped[str] = mapped_column(
        ForeignKey("categoria.pluggy_id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # Cópia denormalizada de `orcamento.tipo` no momento da materialização — evita join por
    # linha em `orcamento_consumo` e entra na unicidade (uma categoria pode ter linha de
    # despesa E de receita no mesmo mês).
    tipo: Mapped[str] = mapped_column(String(16), nullable=False)  # despesa | receita
    ano: Mapped[int] = mapped_column(Integer, nullable=False)
    mes: Mapped[int] = mapped_column(Integer, nullable=False)
    limite_centavos: Mapped[int] = mapped_column(BigInteger, nullable=False)
    editado_manualmente: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Categoria removida só **deste mês** (via "Editar mês"), sem mexer no orçamento padrão —
    # a linha continua existindo (protege contra a materialização recriá-la) mas some da Visão
    # Geral. Fica restrita a este (ano, mes); o mês seguinte materializa uma linha nova, normal.
    suprimido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
