"""Contas (§4.2) — origem `accounts.json`. Dado do Pluggy (sync escreve, usuário lê).

Campo gravável pelo usuário: `objetivo_id` (vínculo 1:1-max #4). Upsert por `pluggy_account_id`
(idempotência do sync da Fase 1) — o sync nunca toca esse campo.

`instituicao_manual_id` NÃO é uma coluna aqui — é computada a partir de `item.instituicao_manual_id`
(a instituição manual vale por CONEXÃO, escolhida ao criar/editar o `ItemPluggy`, não por conta).
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
    from app.models.pluggy import ItemPluggy


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

    # Campo do usuário (§4 crud.md): vínculo a objetivo (0..1, #4).
    objetivo_id: Mapped[int | None] = mapped_column(
        ForeignKey("objetivo.id", ondelete="SET NULL"), index=True
    )

    pluggy_criado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pluggy_atualizado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Detalhe 1:1 do cartão (só CREDIT). viewonly/selectin: a listagem expõe brand/level (arte do
    # cartão) sem N+1 e sem migration. O sync escreve `cartao` pela tabela, não por aqui.
    cartao: Mapped["Cartao | None"] = relationship(viewonly=True, lazy="selectin", uselist=False)
    # A conexão dona da conta — só para ler a instituição manual (mesmo padrão de `cartao`: viewonly
    # + selectin, sem N+1 na listagem).
    item: Mapped["ItemPluggy"] = relationship(viewonly=True, lazy="selectin")

    @property
    def brand(self) -> str | None:
        return self.cartao.brand if self.cartao else None

    @property
    def level(self) -> str | None:
        return self.cartao.level if self.cartao else None

    @property
    def instituicao_manual_id(self) -> int | None:
        """Instituição escolhida à mão para a CONEXÃO (não por conta) — sobrepõe `instituicao_id`
        (a original do sync) na exibição de todas as contas do mesmo item."""
        return self.item.instituicao_manual_id if self.item else None
