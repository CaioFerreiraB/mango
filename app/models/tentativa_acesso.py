"""Freio de forca-bruta na autenticacao (§5.2). Conta falhas por chave e bloqueia por um tempo.

Persistido em banco, nao em memoria: assim vale entre workers e sobrevive a um restart dentro da
janela. Em memoria, cada processo contaria sozinho e o atacante ganharia N vezes mais tentativas.

A `chave` e opaca e o chamador decide quais usar (ver `app/services/tentativas.py`): por e-mail
protege a vitima de um ataque dirigido; por IP corta o spray de varias contas da mesma origem.
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TentativaAcesso(Base):
    __tablename__ = "tentativa_acesso"

    chave: Mapped[str] = mapped_column(String(320), primary_key=True)
    falhas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Inicio da janela corrente: falha fora dela reinicia a contagem em vez de acumular pra sempre.
    janela_inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    bloqueado_ate: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
