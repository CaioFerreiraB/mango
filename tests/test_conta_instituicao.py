"""Vínculo manual da conta a uma instituição (catálogo do Pluggy) + logo.

Cobre: criar o vínculo (sem tocar a instituição original), preservação no re-sync,
desvínculo, e a listagem do catálogo de connectors (com PluggyClient mockado).
"""

from sqlalchemy.orm import Session

from app.models.pluggy import Instituicao
from app.models.usuario import Usuario
from app.repositories.conta import ContaRepository
from app.services import conta as conta_service
from tests.helpers import criar_conta


def test_vincular_instituicao_manual_nao_toca_a_original(
    client_factory, db: Session, usuario_a: Usuario
) -> None:
    conta = criar_conta(db, usuario_a.id, "acc-inst")
    original_id = conta.instituicao_id
    client = client_factory(usuario_a)

    resp = client.put(
        f"/api/contas/{conta.id}/instituicao",
        json={"pluggy_connector_id": 612, "nome": "Nubank", "logo_url": "http://x/nu.png"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["instituicao_id"] == original_id  # original intacta
    manual_id = body["instituicao_manual_id"]
    assert manual_id is not None and manual_id != original_id

    manual = db.get(Instituicao, manual_id)
    assert manual.nome == "Nubank"
    assert manual.logo_url == "http://x/nu.png"
    assert manual.pluggy_connector_id == 612


def test_resync_preserva_vinculo_manual(db: Session, usuario_a: Usuario) -> None:
    conta = criar_conta(db, usuario_a.id, "acc-resync")
    conta_service.vincular_instituicao(db, usuario_a.id, conta.id, 612, "Nubank", "http://x/nu.png")
    manual_id = conta.instituicao_manual_id
    assert manual_id is not None

    # Re-sync (novo saldo, mesma pluggy_account_id) não escreve o campo manual → preservado.
    conta2 = ContaRepository(db, usuario_a.id).upsert_by_pluggy_id(
        "acc-resync",
        item_id=conta.item_id,
        instituicao_id=conta.instituicao_id,
        type="BANK",
        subtype="CHECKING_ACCOUNT",
        saldo_centavos=99999,
        currency_code="BRL",
    )
    assert conta2.id == conta.id
    assert conta2.saldo_centavos == 99999
    assert conta2.instituicao_manual_id == manual_id


def test_desvincular_instituicao(client_factory, db: Session, usuario_a: Usuario) -> None:
    conta = criar_conta(db, usuario_a.id, "acc-unlink")
    conta_service.vincular_instituicao(db, usuario_a.id, conta.id, 612, "Nubank", "http://x/nu.png")
    client = client_factory(usuario_a)

    resp = client.put(f"/api/contas/{conta.id}/instituicao", json={"pluggy_connector_id": None})
    assert resp.status_code == 200, resp.text
    assert resp.json()["instituicao_manual_id"] is None


def test_listar_connectores_catalogo_curado(
    client_factory, db: Session, usuario_a: Usuario
) -> None:
    client = client_factory(usuario_a)
    resp = client.get("/api/pluggy/connectores")
    assert resp.status_code == 200, resp.text
    itens = resp.json()
    nomes = {c["nome"] for c in itens}
    # cobre os bancos que o usuário citou, todos com logo.
    assert {"Nubank", "Itaú", "C6 Bank", "Bradesco"} <= nomes
    assert all(c["logo_url"] for c in itens)
    nubank = next(c for c in itens if c["nome"] == "Nubank")
    assert nubank["logo_url"] == "https://cdn.pluggy.ai/assets/connector-icons/212.svg"


def test_listar_connectores_filtra_por_nome(
    client_factory, db: Session, usuario_a: Usuario
) -> None:
    client = client_factory(usuario_a)
    resp = client.get("/api/pluggy/connectores", params={"nome": "nu"})
    assert resp.status_code == 200, resp.text
    nomes = {c["nome"] for c in resp.json()}
    assert "Nubank" in nomes
    assert "Bradesco" not in nomes
