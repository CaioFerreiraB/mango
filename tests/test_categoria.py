"""Categoria — referência global read-only exposta pela API (§4.5)."""

from sqlalchemy.orm import Session

from app.models.categoria import Categoria
from app.models.usuario import Usuario


def test_categorias_sao_globais_e_read_only(
    client_factory, db: Session, usuario_a: Usuario, usuario_b: Usuario
) -> None:
    db.add(Categoria(pluggy_id="01000000", description="Income", description_translated="Renda"))
    db.commit()

    # Ambos os usuários enxergam a mesma taxonomia (não é filtrada por usuário).
    for user in (usuario_a, usuario_b):
        client = client_factory(user)
        listagem = client.get("/api/categorias").json()
        assert any(c["pluggy_id"] == "01000000" for c in listagem)
        assert client.get("/api/categorias/01000000").json()["description_translated"] == "Renda"

    # Sem endpoints de escrita.
    client = client_factory(usuario_a)
    assert client.post("/api/categorias", json={}).status_code == 405
