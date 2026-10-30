"""Limite transacional para operações compostas que reutilizam serviços existentes."""

from contextlib import contextmanager

from sqlalchemy.orm import Session


def commit(db: Session) -> None:
    if db.info.get("operacao_atomica"):
        db.flush()
    else:
        db.commit()


@contextmanager
def atomica(db: Session):
    anterior = db.info.get("operacao_atomica", False)
    db.info["operacao_atomica"] = True
    try:
        yield
        if not anterior:
            db.commit()
    except Exception:
        if not anterior:
            db.rollback()
        raise
    finally:
        db.info["operacao_atomica"] = anterior
