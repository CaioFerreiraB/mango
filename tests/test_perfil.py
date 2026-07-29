"""Preferências do sistema no perfil (accent + avatar): leitura, atualização e validação;
+ token brapi write-only, cifrado em repouso e nunca devolvido (§5.5)."""

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.models.usuario import Usuario
from app.schemas.perfil import PerfilRead
from app.services.brapi import token_brapi


def test_preferencias_padrao_nulas(client_factory, usuario_a: Usuario) -> None:
    client = client_factory(usuario_a)

    perfil = client.get("/api/perfil").json()
    assert perfil["accent"] is None and perfil["avatar"] is None

    me = client.get("/api/auth/me").json()
    assert me["accent"] is None and me["avatar"] is None


def test_atualiza_preferencias(client_factory, usuario_a: Usuario, db: Session) -> None:
    client = client_factory(usuario_a)

    patch = client.patch("/api/perfil", json={"accent": "manga", "avatar": 2})
    assert patch.status_code == 200, patch.text
    assert patch.json()["accent"] == "manga" and patch.json()["avatar"] == 2

    # Persistência real (o /me do harness devolve o objeto injetado, não relê do banco).
    db.expire_all()
    fresh = db.get(Usuario, usuario_a.id)
    assert fresh is not None and fresh.accent == "manga" and fresh.avatar == 2


def test_preferencias_invalidas_rejeitadas(client_factory, usuario_a: Usuario) -> None:
    client = client_factory(usuario_a)

    assert client.patch("/api/perfil", json={"accent": "magenta"}).status_code == 422
    assert client.patch("/api/perfil", json={"avatar": 5}).status_code == 422
    assert client.patch("/api/perfil", json={"avatar": 0}).status_code == 422


# --- token brapi (§4.9): write-only, cifrado, nunca devolvido -------------------------

_TOKEN = "meu-token-brapi-secreto-123"


def test_brapi_token_write_only_cifrado_e_nunca_devolvido(
    client_factory, usuario_a: Usuario, db: Session
) -> None:
    client = client_factory(usuario_a)
    assert client.get("/api/perfil").json()["brapi_token_configurado"] is False

    assert client.put("/api/perfil/brapi-token", json={"token": _TOKEN}).status_code == 204

    # Persistência (o harness devolve o objeto injetado, não relê do banco — como em preferências).
    db.expire_all()
    fresh = db.get(Usuario, usuario_a.id)
    assert fresh is not None and fresh.brapi_token_configurado is True

    # O schema de leitura expõe só o booleano — o segredo nunca é serializado.
    dump = PerfilRead.model_validate(fresh).model_dump()
    assert dump["brapi_token_configurado"] is True
    assert "brapi_token_cifrado" not in dump and _TOKEN not in str(dump)
    # E nenhuma resposta da API carrega o token (perfil nem /me).
    assert _TOKEN not in client.get("/api/perfil").text
    assert _TOKEN not in client.get("/api/auth/me").text

    # Em repouso está cifrado (o valor cru da coluna ≠ texto puro; é um token Fernet).
    sql = text("SELECT brapi_token_cifrado FROM usuario WHERE id = :id")
    cru = db.scalar(sql, {"id": usuario_a.id})
    assert cru is not None and cru != _TOKEN and cru.startswith("gAAAAA")


def test_brapi_token_resolver_usuario_depois_ambiente(
    client_factory, usuario_a: Usuario, db: Session, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "brapi_token", "token-do-ambiente")
    # Sem token no perfil → cai no ambiente.
    assert token_brapi(db, usuario_a.id) == "token-do-ambiente"

    client_factory(usuario_a).put("/api/perfil/brapi-token", json={"token": _TOKEN})
    db.expire_all()
    assert token_brapi(db, usuario_a.id) == _TOKEN  # o do perfil tem precedência


def test_brapi_token_removido(client_factory, usuario_a: Usuario, db: Session) -> None:
    client = client_factory(usuario_a)
    client.put("/api/perfil/brapi-token", json={"token": _TOKEN})
    assert client.delete("/api/perfil/brapi-token").status_code == 204
    assert client.get("/api/perfil").json()["brapi_token_configurado"] is False
    db.expire_all()
    assert token_brapi(db, usuario_a.id) == settings.brapi_token
