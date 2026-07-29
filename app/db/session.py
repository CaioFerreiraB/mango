"""Engine/Session. SQLite recebe PRAGMA foreign_keys=ON (FK valem) + WAL (§5.4)."""

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings


def create_db_engine(url: str) -> Engine:
    """Cria o engine para `url`, ligando os PRAGMAs do SQLite quando aplicável."""
    is_sqlite = url.startswith("sqlite")
    connect_args = {"check_same_thread": False} if is_sqlite else {}
    eng = create_engine(url, connect_args=connect_args, future=True)

    if is_sqlite:

        @event.listens_for(eng, "connect")
        def _set_sqlite_pragma(dbapi_conn, _record):  # noqa: ANN001
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA journal_mode=WAL")
            cur.close()

    return eng


engine = create_db_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Iterator[Session]:
    """Dependency do FastAPI: abre uma Session por request e fecha no fim."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
