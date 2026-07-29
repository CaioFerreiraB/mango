"""Isolamento na camada de repositório (§5.2) — independente da API."""

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.pluggy import CredencialPluggy
from app.models.usuario import Usuario
from app.repositories.fonte_de_renda import FonteDeRendaRepository


def test_repositorio_filtra_por_usuario(
    db: Session, usuario_a: Usuario, usuario_b: Usuario
) -> None:
    repo_a = FonteDeRendaRepository(db, usuario_a.id)
    repo_b = FonteDeRendaRepository(db, usuario_b.id)

    fonte = repo_a.create(
        nome="Salário", tipo="fixa", valor_estimado_centavos=1000, recorrencia="mensal", fonte=None
    )

    # B não enxerga nem altera a linha de A.
    assert repo_b.list() == []
    assert repo_b.get(fonte.id) is None
    # A enxerga a própria.
    assert repo_a.get(fonte.id).id == fonte.id


def test_credencial_cifrada_em_repouso(db: Session, usuario_a: Usuario) -> None:
    cred = CredencialPluggy(
        usuario_id=usuario_a.id,
        client_id_cifrado="meu-client-id",
        client_secret_cifrado="meu-secret",
    )
    db.add(cred)
    db.commit()
    db.refresh(cred)

    # Leitura volta em claro (decifrada transparente).
    assert cred.client_secret_cifrado == "meu-secret"

    # No banco, o valor está cifrado — texto puro não aparece (§5.5).
    raw = db.execute(
        text("SELECT client_secret_cifrado FROM credencial_pluggy WHERE id = :i"),
        {"i": cred.id},
    ).scalar_one()
    assert raw != "meu-secret"
    assert "meu-secret" not in raw
