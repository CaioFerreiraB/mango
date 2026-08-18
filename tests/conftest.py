"""Fixtures de teste — rodam contra SQLite e PostgreSQL (paridade de dialeto, §5.4).

O parâmetro `engine` roda cada teste nos dois bancos. Postgres é pulado se indisponível
(local sem `docker compose up -d db`); no CI ele sempre está de pé.
"""

import os
from collections.abc import Callable, Iterator

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401 — carrega toda a metadata antes do create_all
from app.db.base import Base
from app.db.session import create_db_engine, get_db
from app.main import app as fastapi_app
from app.models.usuario import Usuario
from app.security.current_user import get_current_user

PG_DEFAULT = "postgresql+psycopg://mango:mango@localhost:5432/mango"


@pytest.fixture(params=["sqlite", "postgres"])
def engine(request: pytest.FixtureRequest, tmp_path) -> Iterator[Engine]:
    if request.param == "sqlite":
        url = f"sqlite:///{tmp_path}/test.db"
    else:
        url = os.environ.get("TEST_DATABASE_URL", PG_DEFAULT)

    eng = create_db_engine(url)
    try:
        with eng.connect():
            pass
    except Exception:
        eng.dispose()
        pytest.skip(f"banco indisponível para o dialeto: {request.param}")

    # drop antes de create torna o setup idempotente (limpa resíduo de run anterior).
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    # SQLite: arquivo temporário é descartado pelo pytest; um drop_all com FK=ON falha ao
    # apagar `categoria` (auto-FK). Postgres (banco compartilhado) precisa do drop.
    if not url.startswith("sqlite"):
        Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture
def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@pytest.fixture
def db(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def _criar_usuario(db: Session, nome: str, email: str, **campos) -> Usuario:
    user = Usuario(nome=nome, email=email, **campos)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def usuario_a(db: Session) -> Usuario:
    return _criar_usuario(db, "Usuário A", "a@mango.test")


@pytest.fixture
def usuario_b(db: Session) -> Usuario:
    return _criar_usuario(db, "Usuário B", "b@mango.test")


@pytest.fixture
def usuario_admin(db: Session) -> Usuario:
    """Dono da instância (§4.11) — só ele acessa a gestão de usuários (`require_admin`)."""
    return _criar_usuario(db, "Admin", "admin@mango.test", is_admin=True)


@pytest.fixture
def client_factory(
    session_factory: sessionmaker[Session],
) -> Iterator[Callable[[Usuario], TestClient]]:
    """Cria TestClients autenticados como `user`.

    O usuário atual é resolvido por request (header `x-test-user`), e não por um override
    global — assim clientes de A e B coexistem (essencial p/ os testes de isolamento).
    """
    registro: dict[int, Usuario] = {}

    def _get_db() -> Iterator[Session]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    def _usuario_atual(request: Request) -> Usuario:
        return registro[int(request.headers["x-test-user"])]

    fastapi_app.dependency_overrides[get_db] = _get_db
    fastapi_app.dependency_overrides[get_current_user] = _usuario_atual

    def _factory(user: Usuario) -> TestClient:
        registro[user.id] = user
        return TestClient(fastapi_app, headers={"x-test-user": str(user.id)})

    yield _factory
    fastapi_app.dependency_overrides.clear()


@pytest.fixture
def client_factory_sh(
    client_factory: Callable[[Usuario], TestClient], monkeypatch: pytest.MonkeyPatch
) -> Callable[[Usuario], TestClient]:
    """`client_factory` em modo self-hosted, com o double-submit de CSRF já satisfeito.

    `client_factory` não faz login de verdade (usuário atual vem do header `x-test-user`, sem
    sessão) — em self-hosted, o middleware de CSRF (`app.security.csrf`) exige cookie `mango_csrf`
    == header `X-CSRF-Token` em toda mutação, e não há cookie genuíno pra ecoar. Simula o par só
    pra destravar os testes que precisam de self-hosted (ex.: `require_admin`, que 404 fora dele).
    """
    from app.config import settings
    from app.security.sessions import CSRF_COOKIE, CSRF_HEADER

    monkeypatch.setattr(settings, "app_mode", "self_hosted")

    def _factory(user: Usuario) -> TestClient:
        client = client_factory(user)
        client.cookies.set(CSRF_COOKIE, "teste")
        client.headers[CSRF_HEADER] = "teste"
        return client

    return _factory


class _PluggyOk:
    """Duplo do `PluggyClient` para o setup: credencial e itemId sempre válidos, sem rede."""

    def __enter__(self) -> "_PluggyOk":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def autenticar(self) -> str:
        return "api-key-de-teste"

    def item(self, item_id: str) -> dict:
        return {"id": item_id}


@pytest.fixture
def sh_client(
    session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    """Client em modo self-hosted numa DB limpa, para os fluxos de setup/auth (sem sessão prévia).

    `session_cookie_secure=False` deixa o TestClient (http) guardar os cookies; a auth real roda
    (não sobrescrevemos `get_current_user`), só o `get_db` aponta para a DB de teste. O Pluggy do
    setup (validação ao vivo da conexão) vem dublado — quem testa a falha repõe o patch.
    """
    from app.config import settings
    from app.services import setup as setup_service

    monkeypatch.setattr(settings, "app_mode", "self_hosted")
    monkeypatch.setattr(settings, "session_cookie_secure", False)
    monkeypatch.setattr(setup_service, "PluggyClient", lambda *a, **k: _PluggyOk())

    def _get_db() -> Iterator[Session]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    fastapi_app.dependency_overrides[get_db] = _get_db
    yield TestClient(fastapi_app)
    fastapi_app.dependency_overrides.clear()
