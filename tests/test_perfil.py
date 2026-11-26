"""Preferências do sistema no perfil (accent, avatar, corte da revisão): leitura, atualização e
validação; + token brapi write-only, cifrado em repouso e nunca devolvido (§5.5)."""

from datetime import date

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

    patch = client.patch("/api/perfil", json={"accent": "tangerina", "avatar": 2})
    assert patch.status_code == 200, patch.text
    assert patch.json()["accent"] == "tangerina" and patch.json()["avatar"] == 2

    # Persistência real (o /me do harness devolve o objeto injetado, não relê do banco).
    db.expire_all()
    fresh = db.get(Usuario, usuario_a.id)
    assert fresh is not None and fresh.accent == "tangerina" and fresh.avatar == 2


def test_preferencias_invalidas_rejeitadas(client_factory, usuario_a: Usuario) -> None:
    client = client_factory(usuario_a)

    assert client.patch("/api/perfil", json={"accent": "magenta"}).status_code == 422
    assert client.patch("/api/perfil", json={"avatar": 5}).status_code == 422
    assert client.patch("/api/perfil", json={"avatar": 0}).status_code == 422


# --- data de corte da revisão (§4.3) --------------------------------------------------


def test_revisao_desde_grava_e_limpa(client_factory, usuario_a: Usuario, db: Session) -> None:
    client = client_factory(usuario_a)
    assert client.get("/api/perfil").json()["revisao_desde"] is None  # sem corte por padrão

    patch = client.patch("/api/perfil", json={"revisao_desde": "2026-03-01"})
    assert patch.status_code == 200, patch.text
    assert patch.json()["revisao_desde"] == "2026-03-01"

    db.expire_all()
    fresh = db.get(Usuario, usuario_a.id)
    assert fresh is not None and fresh.revisao_desde == date(2026, 3, 1)

    # Limpar volta ao "todo o histórico pede revisão".
    assert client.patch("/api/perfil", json={"revisao_desde": None}).json()["revisao_desde"] is None
    db.expire_all()
    fresh = db.get(Usuario, usuario_a.id)
    assert fresh is not None and fresh.revisao_desde is None


def test_revisao_desde_invalida_rejeitada(client_factory, usuario_a: Usuario) -> None:
    client = client_factory(usuario_a)
    assert client.patch("/api/perfil", json={"revisao_desde": "01/03/2026"}).status_code == 422
    assert client.patch("/api/perfil", json={"revisao_desde": "2026-02-30"}).status_code == 422


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


def test_dashboard_layout_round_trip_e_restaurar(
    client_factory, usuario_a: Usuario, db: Session
) -> None:
    client = client_factory(usuario_a)
    assert client.get("/api/perfil").json()["dashboard_layout"] is None  # padrão

    def gravado():
        # O /perfil do harness devolve o objeto injetado; a persistência real se lê do banco.
        db.expire_all()
        return db.get(Usuario, usuario_a.id).dashboard_layout

    layout = [
        {"id": "fluxo", "largura": 60, "visivel": True},
        {"id": "kpi-saldo", "largura": 12, "visivel": False},
        {"id": "rec-fontes", "largura": 36, "altura": 320, "visivel": True},
    ]
    r = client.patch("/api/perfil", json={"dashboard_layout": layout})
    assert r.status_code == 200, r.text
    assert r.json()["dashboard_layout"] == layout
    assert gravado() == layout

    # Outro campo no PATCH não mexe no layout (exclude_unset).
    client.patch("/api/perfil", json={"accent": "lima"})
    assert gravado() == layout

    r = client.patch("/api/perfil", json={"dashboard_layout": None})
    assert r.status_code == 200 and r.json()["dashboard_layout"] is None
    assert gravado() is None


def test_dashboard_layout_valida_fronteira(client_factory, usuario_a: Usuario) -> None:
    client = client_factory(usuario_a)
    w = {"id": "fluxo", "largura": 60, "visivel": True}
    invalidos = [
        [w, w],  # id repetido
        [{**w, "largura": 6}],  # largura fora do enum (grid antigo de 12)
        [{**w, "id": "<script>"}],  # id fora do padrão
        [{**w, "altura": 50}],  # altura abaixo do mínimo
        [{**w, "id": f"w-{chr(97 + i % 26)}{'a' * (i // 26)}"} for i in range(61)],  # > 60
    ]
    for layout in invalidos:
        r = client.patch("/api/perfil", json={"dashboard_layout": layout})
        assert r.status_code == 422, layout
    assert client.get("/api/perfil").json()["dashboard_layout"] is None


def test_atalhos_mobile_round_trip_e_fronteira(
    client_factory, usuario_a: Usuario, db: Session
) -> None:
    client = client_factory(usuario_a)
    assert client.get("/api/perfil").json()["atalhos_mobile"] is None  # padrão

    def gravado():
        db.expire_all()
        return db.get(Usuario, usuario_a.id).atalhos_mobile

    atalhos = ["chat", "contas", "objetivos"]
    r = client.patch("/api/perfil", json={"atalhos_mobile": atalhos})
    assert r.status_code == 200, r.text
    assert r.json()["atalhos_mobile"] == atalhos
    assert gravado() == atalhos

    for invalido in (
        ["chat", "chat"],  # repetido
        ["a", "b", "c", "d"],  # > 3 (o Início é fixo)
        ["<script>"],  # fora do padrão
    ):
        r = client.patch("/api/perfil", json={"atalhos_mobile": invalido})
        assert r.status_code == 422, invalido
    assert gravado() == atalhos

    r = client.patch("/api/perfil", json={"atalhos_mobile": None})
    assert r.status_code == 200 and gravado() is None
