"""Token brapi.dev efetivo do usuário: o gravado no perfil (cifrado em repouso, §5.5) senão o
fallback do ambiente (`settings.brapi_token`). O segredo nunca sai da API — só é lido aqui p/ falar
com a brapi. `select` da coluna `EncryptedStr` já devolve o texto decifrado."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.usuario import Usuario


def token_brapi(db: Session, usuario_id: int) -> str:
    token = db.scalar(select(Usuario.brapi_token_cifrado).where(Usuario.id == usuario_id))
    return token or settings.brapi_token
