from app.models.usuario import Usuario


def test_health(client_factory, usuario_a: Usuario) -> None:
    client = client_factory(usuario_a)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
