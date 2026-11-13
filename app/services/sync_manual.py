"""Sync manual (botão "Atualizar") em segundo plano, com status consultável pela UI (§4.3).

O tempo do sync depende do Pluggy (1 request por investimento, até 120s por 429) e estourava o
timeout do reverse proxy quando rodava dentro do request. A rota só valida o escopo e dispara;
a UI acompanha por `status_sync`.

`ponytail:` status em memória por processo (mesma premissa do lock de `app.services.sync`: 1
worker); multi-worker exigiria levar o status p/ uma tabela. Some no restart — o usuário só reclica.
"""

import logging
import threading
from dataclasses import asdict
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.exceptions import ConflictError, DomainError, NotFoundError
from app.pluggy.client import PluggyError
from app.repositories.pluggy import CredencialPluggyRepository, ItemPluggyRepository
from app.services.sync import sincronizar_usuario

logger = logging.getLogger("app.sync")

_lock = threading.Lock()
_status: dict[int, dict] = {}  # por usuário, protegido por `_lock`


def status_sync(usuario_id: int) -> dict:
    with _lock:
        return dict(_status.get(usuario_id) or {"em_andamento": False})


def iniciar_sync(db: Session, usuario_id: int, item_id: int | None = None) -> dict:
    """Valida o escopo no request (404 imediato, S3) e roda o sync numa thread de fundo."""
    if not CredencialPluggyRepository(db, usuario_id).list():
        raise NotFoundError("nenhuma credencial Pluggy configurada")
    if item_id is not None and ItemPluggyRepository(db, usuario_id).get(item_id) is None:
        raise NotFoundError("conexão não encontrada")
    with _lock:
        if (_status.get(usuario_id) or {}).get("em_andamento"):
            raise ConflictError("sincronização já está em andamento")
        _status[usuario_id] = {"em_andamento": True}
    threading.Thread(
        target=_rodar_em_fundo, args=(usuario_id, item_id), daemon=True, name="sync-manual"
    ).start()
    # Não relê `_status`: a thread pode terminar antes e o POST só garante que o sync começou.
    return {"em_andamento": True}


def _rodar_em_fundo(usuario_id: int, item_id: int | None) -> None:
    resumo, erro = None, None
    try:
        with SessionLocal() as db:
            resumo = asdict(sincronizar_usuario(db, usuario_id, item_id=item_id))
    except PluggyError as exc:
        # Ao cliente vai só a mensagem genérica (o detalhe do Pluggy pode conter dado interno).
        # Ao log vai o detalhe já redigido do PluggyError (só método/rota/status) p/ diagnóstico.
        logger.warning("sync falhou (usuario=%s, item=%s): %s", usuario_id, item_id, exc)
        erro = "não foi possível falar com o Pluggy agora"
    except DomainError as exc:
        erro = exc.mensagem
    except Exception:
        logger.exception("sync falhou (usuario=%s, item=%s)", usuario_id, item_id)
        erro = "erro inesperado ao sincronizar"
    with _lock:
        _status[usuario_id] = {
            "em_andamento": False,
            "resumo": resumo,
            "erro": erro,
            "concluido_em": datetime.now(UTC),
        }
