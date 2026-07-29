"""Contas (§4.2) — origem `accounts.json`. Dado do Pluggy (sync escreve, usuário lê).

Campos graváveis pelo usuário: `objetivo_id` (vínculo 1:1-max #4) e `instituicao_manual_id`
(instituição escolhida à mão, sobrepõe a original só na exibição). Upsert por
`pluggy_account_id` (idempotência do sync da Fase 1) — o sync nunca toca esses dois campos.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.enums import CONTA_SUBTYPE, CONTA_TYPE, check_in
from app.models.mixins import TimestampMixin, UserOwnedMixin

if TYPE_CHECKING:
    from app.models.cartao_fatura import Cartao


class Conta(UserOwnedMixin, TimestampMixin, Base):
    __tablename__ = "conta"
    __table_args__ = (
        check_in("type", CONTA_TYPE, "type"),
        check_in("subtype", CONTA_SUBTYPE, "subtype"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("item_pluggy.id", ondelete="CASCADE"), nullable=False, index=True
    )
    instituicao_id: Mapped[int] = mapped_column(
        ForeignKey("instituicao.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    pluggy_account_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    type: Mapped[str] = mapped_column(String(16), nullable=False)  # BANK | CREDIT
    subtype: Mapped[str | None] = mapped_column(String(32))
    nome: Mapped[str | None] = mapped_column(String(255))
    marketing_name: Mapped[str | None] = mapped_column(String(255))
    numero: Mapped[str | None] = mapped_column(String(64))
    owner: Mapped[str | None] = mapped_column(String(255))
    tax_number: Mapped[str | None] = mapped_column(String(32))
    saldo_centavos: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, default="BRL")

    # Campos do usuário (§4 crud.md): vínculo a objetivo (0..1, #4) e instituição manual.
    objetivo_id: Mapped[int | None] = mapped_column(
        ForeignKey("objetivo.id", ondelete="SET NULL"), index=True
    )
    # Instituição escolhida à mão (o connector do Pluggy é sempre "meu Pluggy"). Quando setada,
    # é a instituição efetiva (exibição/filtro); senão cai na `instituicao_id` do sync.
    instituicao_manual_id: Mapped[int | None] = mapped_column(
        ForeignKey("instituicao.id", ondelete="SET NULL"), index=True
    )

    pluggy_criado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pluggy_atualizado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Detalhe 1:1 do cartão (só CREDIT). viewonly/selectin: a listagem expõe brand/level (arte do
    # cartão) sem N+1 e sem migration. O sync escreve `cartao` pela tabela, não por aqui.
    cartao: Mapped["Cartao | None"] = relationship(viewonly=True, lazy="selectin", uselist=False)

    @property
    def brand(self) -> str | None:
        return self.cartao.brand if self.cartao else None

    @property
    def level(self) -> str | None:
        return self.cartao.level if self.cartao else None
