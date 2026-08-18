"""Convite de usuário "só divisão" (§4.11, §3) — link copiável, sem e-mail (decisão #15).

Hoje é o ÚNICO caminho para um segundo usuário entrar numa instância self-hosted: `/setup` só
cria o dono, na primeira execução. "Convidar pessoa" (divisão de contas) cria um `Usuario`
placeholder sem senha (`senha_hash IS NULL` = status "só divisão") e este registro, com um token
de ativação — só o hash fica no banco, o token cru é devolvido uma única vez para o link.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ConviteUsuario(Base):
    __tablename__ = "convite_usuario"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False, index=True
    )
    criado_por_usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    usado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
