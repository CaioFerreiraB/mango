"""Vínculo manual de instituição na CONEXÃO (item_pluggy) + logo.

Cobre: criar o vínculo no item (sem tocar a instituição original das contas), o vínculo valer
para TODAS as contas do mesmo item, preservação no re-sync, desvínculo, e a listagem do
catálogo de connectors (com PluggyClient mockado).
"""

from sqlalchemy.orm import Session

from app.models.pluggy import Instituicao
from app.models.usuario import Usuario
from app.repositories.conta import ContaRepository
from app.services import item as item_service
from tests.helpers import criar_conta, criar_conta_no_item, criar_prereqs_conta


def test_vincular_instituicao_manual_do_item_nao_toca_a_original(
    client_factory, db: Session, usuario_a: Usuario
) -> None:
    conta = criar_conta(db, usuario_a.id, "acc-inst")
    original_id = conta.instituicao_id
    client = client_factory(usuario_a)

    resp = client.put(
        f"/api/itens-pluggy/{conta.item_id}/instituicao",
        json={"pluggy_connector_id": 612, "nome": "Nubank", "logo_url": "http://x/nu.png"},
    )
    assert resp.status_code == 200, resp.text
    manual_id = resp.json()["instituicao_manual_id"]
    assert manual_id is not None and manual_id != original_id

    manual = db.get(Instituicao, manual_id)
    assert manual.nome == "Nubank"
    assert manual.logo_url == "http://x/nu.png"
    assert manual.pluggy_connector_id == 612

    conta_resp = client.get(f"/api/contas/{conta.id}")
    assert conta_resp.json()["instituicao_id"] == original_id  # original intacta
    assert conta_resp.json()["instituicao_manual_id"] == manual_id


def test_vinculo_do_item_propaga_para_todas_as_contas(
    client_factory, db: Session, usuario_a: Usuario
) -> None:
    inst, item = criar_prereqs_conta(db, usuario_a.id)
    conta1 = criar_conta_no_item(db, usuario_a.id, item, inst, "acc-1")
    conta2 = criar_conta_no_item(db, usuario_a.id, item, inst, "acc-2")
    client = client_factory(usuario_a)

    resp = client.put(
        f"/api/itens-pluggy/{item.id}/instituicao",
        json={"pluggy_connector_id": 612, "nome": "Nubank", "logo_url": "http://x/nu.png"},
    )
    assert resp.status_code == 200, resp.text
    manual_id = resp.json()["instituicao_manual_id"]

    contas = {c["id"]: c for c in client.get("/api/contas").json()}
    assert contas[conta1.id]["instituicao_manual_id"] == manual_id
    assert contas[conta2.id]["instituicao_manual_id"] == manual_id


def test_resync_preserva_vinculo_manual_do_item(db: Session, usuario_a: Usuario) -> None:
    conta = criar_conta(db, usuario_a.id, "acc-resync")
    item_service.vincular_instituicao(
        db, usuario_a.id, conta.item_id, 612, "Nubank", "http://x/nu.png"
    )
    manual_id = conta.instituicao_manual_id
    assert manual_id is not None

    # Re-sync (novo saldo, mesma pluggy_account_id) não mexe no item → vínculo preservado.
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


def test_desvincular_instituicao_do_item(client_factory, db: Session, usuario_a: Usuario) -> None:
    conta = criar_conta(db, usuario_a.id, "acc-unlink")
    item_service.vincular_instituicao(
        db, usuario_a.id, conta.item_id, 612, "Nubank", "http://x/nu.png"
    )
    client = client_factory(usuario_a)

    resp = client.put(
        f"/api/itens-pluggy/{conta.item_id}/instituicao", json={"pluggy_connector_id": None}
    )
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
