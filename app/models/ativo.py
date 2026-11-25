"""Ativo — agrupa N posições `investimento` do mesmo papel de renda fixa (várias compras de
"Tesouro Selic 2028", p.ex.) sob um nome editável. Resultado do ativo = soma das posições.
Entidade do usuário (não vem do Pluggy): renda variável já agrupa por `code`; FII e fundos não usam.

`objetivo_id` é a fonte da verdade do vínculo a objetivo (#4) para as compras do ativo: compra
nova, movida para cá ou criada pelo sync herda o vínculo. `investimento.objetivo_id` das compras
com ativo é só espelho (`sincronizar_objetivos_ativos`).
"""

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UserOwnedMixin


class Ativo(UserOwnedMixin, TimestampMixin, Base):
    __tablename__ = "ativo"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    objetivo_id: Mapped[int | None] = mapped_column(
        ForeignKey("objetivo.id", ondelete="SET NULL"), index=True
    )
