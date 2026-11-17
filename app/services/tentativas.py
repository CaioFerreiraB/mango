"""Politica de bloqueio por tentativas de autenticacao (§5.2).

Espelha o freio que o axon ja tem: 5 falhas em 15 min bloqueiam aquela chave por 15 min. Uma
tentativa recusada pelo proprio bloqueio NAO conta - senao o atacante estenderia a punicao de
graca e o bloqueio nunca cederia.

Usado no login e na recuperacao de senha: endpoints publicos sem nenhuma outra defesa contra forca
bruta. A recuperacao valida so um TOTP de 6 digitos; sem este freio, o codigo e bruteavel
conhecendo apenas o e-mail (takeover de conta). bcrypt/argon2 nao substituem isto - encarecem cada
tentativa, nao limitam o numero delas.
"""

from datetime import UTC, datetime, timedelta

from fastapi import Request
from sqlalchemy.orm import Session

from app.exceptions import RateLimitError
from app.models.tentativa_acesso import TentativaAcesso

JANELA = timedelta(minutes=15)
MAX_FALHAS = 5
BLOQUEIO = timedelta(minutes=15)


def _aware(momento: datetime) -> datetime:
    return momento if momento.tzinfo else momento.replace(tzinfo=UTC)  # SQLite devolve naive


def chaves_de(email: str, request: Request | None) -> list[str]:
    """As chaves que uma tentativa consome: a vitima (e-mail) e a origem (IP)."""
    ip = request.client.host if request and request.client else "desconhecido"
    return [f"email:{email}", f"ip:{ip}"]


def verificar(db: Session, chaves: list[str]) -> None:
    """429 se qualquer uma das chaves esta bloqueada agora. Chamar ANTES de validar credencial."""
    agora = datetime.now(UTC)
    for chave in chaves:
        t = db.get(TentativaAcesso, chave)
        if t is not None and t.bloqueado_ate is not None and agora < _aware(t.bloqueado_ate):
            raise RateLimitError("muitas tentativas; tente novamente em alguns minutos")


def registrar_falha(db: Session, chaves: list[str]) -> None:
    """Contabiliza uma falha em cada chave; ao atingir o teto na janela, arma o bloqueio."""
    agora = datetime.now(UTC)
    for chave in chaves:
        t = db.get(TentativaAcesso, chave)
        if t is None:
            t = TentativaAcesso(chave=chave, falhas=0, janela_inicio=agora)
            db.add(t)
        if agora - _aware(t.janela_inicio) > JANELA:
            t.falhas, t.janela_inicio, t.bloqueado_ate = 1, agora, None
        else:
            t.falhas += 1
            if t.falhas >= MAX_FALHAS:
                t.bloqueado_ate = agora + BLOQUEIO
    db.commit()


def limpar(db: Session, chaves: list[str]) -> None:
    """Sucesso zera o historico: so a sequencia de falhas consecutivas interessa."""
    for chave in chaves:
        t = db.get(TentativaAcesso, chave)
        if t is not None:
            db.delete(t)
    db.commit()
