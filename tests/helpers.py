"""Helpers de teste — montam pré-requisitos das entidades do Pluggy."""

from sqlalchemy.orm import Session

from app.models.conta import Conta
from app.models.pluggy import CredencialPluggy, Instituicao, ItemPluggy
from app.repositories.conta import ContaRepository


def criar_prereqs_conta(db: Session, usuario_id: int) -> tuple[Instituicao, ItemPluggy]:
    """Cria instituição + credencial + item (cadeia de FKs da conta) para um usuário."""
    inst = Instituicao(usuario_id=usuario_id, nome="Banco Teste", pluggy_connector_id=1)
    cred = CredencialPluggy(
        usuario_id=usuario_id,
        client_id_cifrado="client-id",
        client_secret_cifrado="client-secret",
    )
    db.add_all([inst, cred])
    db.commit()
    db.refresh(inst)
    db.refresh(cred)

    item = ItemPluggy(usuario_id=usuario_id, credencial_id=cred.id, pluggy_item_id="item-1")
    db.add(item)
    db.commit()
    db.refresh(item)
    return inst, item


def criar_conta(db: Session, usuario_id: int, pluggy_account_id: str, **overrides) -> Conta:
    inst, item = criar_prereqs_conta(db, usuario_id)
    campos = {
        "item_id": item.id,
        "instituicao_id": inst.id,
        "type": "BANK",
        "subtype": "CHECKING_ACCOUNT",
        "saldo_centavos": 10000,
        "currency_code": "BRL",
        **overrides,
    }
    return ContaRepository(db, usuario_id).upsert_by_pluggy_id(pluggy_account_id, **campos)
