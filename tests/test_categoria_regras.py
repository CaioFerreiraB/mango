"""Regras de categorização (§4.5): casamento puro, limites e aplicação nas transações."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from app.models.categoria import Categoria
from app.models.transacao import Transacao
from app.models.usuario import Usuario
from app.services.categoria_regras import Regra, aplicar_regras_categorizacao, casar, compilar
from app.services.regra_categorizacao import MAX_REGRAS
from tests.helpers import criar_conta

# --- casamento puro (sem banco) ------------------------------------------------------------


def _compiladas(*regras: tuple[int, str, str, str]):
    return compilar(Regra(i, t, m, c) for i, t, m, c in regras)


def test_exato_exige_nome_inteiro() -> None:
    c = _compiladas((1, "netflix", "exato", "01"))
    assert casar(("Netflix",), c) == "01"
    assert casar(("NETFLIX.COM",), c) is None  # exato não é prefixo
    assert casar((None, "netflix"), c) == "01"


def test_contem_aceita_substring() -> None:
    c = _compiladas((1, "uber", "contem", "02"))
    assert casar(("UBER *TRIP 4521",), c) == "02"
    assert casar(("Uber Eats",), c) == "02"
    assert casar(("Lyft",), c) is None


def test_normalizacao_ignora_caixa_acento_e_espaco_repetido() -> None:
    c = _compiladas((1, "farmacia", "contem", "03"))
    assert casar(("FARMÁCIA  SÃO JOÃO",), c) == "03"
    c_exato = _compiladas((1, "padaria do ze", "exato", "04"))
    assert casar(("  Padaria   do   Zé ",), c_exato) == "04"


def test_exato_vence_contem() -> None:
    c = _compiladas((1, "uber", "contem", "02"), (2, "uber eats", "exato", "05"))
    assert casar(("Uber Eats",), c) == "05"


def test_entre_contem_o_texto_mais_longo_vence() -> None:
    c = _compiladas((1, "uber", "contem", "02"), (2, "uber eats", "contem", "05"))
    assert casar(("UBER EATS 123",), c) == "05"
    assert casar(("UBER TRIP",), c) == "02"


def test_empate_de_comprimento_resolve_pelo_id_mais_antigo() -> None:
    c = _compiladas((7, "abcd", "contem", "07"), (3, "wxyz", "contem", "03"))
    assert casar(("wxyz abcd",), c) == "03"  # mesmo tamanho → id menor vence


def test_casa_merchant_ou_description() -> None:
    c = _compiladas((1, "spotify", "contem", "06"))
    assert casar(("Outro nome", "PAGAMENTO SPOTIFY BR"), c) == "06"


def test_sem_nome_ou_sem_regra_nao_casa() -> None:
    assert casar((None, None), _compiladas((1, "x1y", "contem", "01"))) is None
    assert casar(("Qualquer",), compilar([])) is None


def test_texto_normalizado_vazio_e_ignorado() -> None:
    """Regra degenerada não pode virar `"" in nome`, que casaria tudo."""
    c = _compiladas((1, "   ", "contem", "99"))
    assert casar(("Qualquer coisa",), c) is None


# --- CRUD, validação e limites --------------------------------------------------------------


@pytest.fixture
def categoria(db: Session) -> str:
    db.add(Categoria(pluggy_id="02000000", description="Food", description_translated="Comida"))
    db.commit()
    return "02000000"


def test_crud_completo(client_factory, usuario_a: Usuario, categoria: str) -> None:
    client = client_factory(usuario_a)
    criada = client.post(
        "/api/regras-categorizacao",
        json={"texto": "Netflix", "tipo_match": "exato", "categoria_id": categoria},
    )
    assert criada.status_code == 201, criada.text
    corpo = criada.json()
    assert corpo["texto"] == "Netflix"
    assert "texto_normalizado" not in corpo  # campo interno não é API

    regra_id = corpo["id"]
    assert (
        client.patch(f"/api/regras-categorizacao/{regra_id}", json={"tipo_match": "contem"}).json()[
            "tipo_match"
        ]
        == "contem"
    )
    assert len(client.get("/api/regras-categorizacao").json()) == 1
    assert client.delete(f"/api/regras-categorizacao/{regra_id}").status_code == 204
    assert client.get("/api/regras-categorizacao").json() == []


def test_texto_curto_demais_e_recusado(client_factory, usuario_a: Usuario, categoria: str) -> None:
    """Uma regra "contém" de 1–2 caracteres casaria quase toda transação."""
    client = client_factory(usuario_a)
    for texto in ("a", "ub", "  "):
        resposta = client.post(
            "/api/regras-categorizacao",
            json={"texto": texto, "tipo_match": "contem", "categoria_id": categoria},
        )
        assert resposta.status_code == 422, texto


def test_duplicata_ignora_caixa_e_acento(
    client_factory, usuario_a: Usuario, categoria: str
) -> None:
    client = client_factory(usuario_a)
    base = {"tipo_match": "contem", "categoria_id": categoria}
    assert (
        client.post("/api/regras-categorizacao", json={"texto": "Farmácia", **base}).status_code
        == 201
    )
    assert (
        client.post("/api/regras-categorizacao", json={"texto": "farmacia", **base}).status_code
        == 409
    )
    # Mesmo texto com OUTRO tipo de match é regra distinta e é permitido.
    assert (
        client.post(
            "/api/regras-categorizacao",
            json={"texto": "Farmácia", "tipo_match": "exato", "categoria_id": categoria},
        ).status_code
        == 201
    )


def test_tipo_match_invalido_e_recusado(client_factory, usuario_a: Usuario, categoria: str) -> None:
    client = client_factory(usuario_a)
    resposta = client.post(
        "/api/regras-categorizacao",
        json={"texto": "netflix", "tipo_match": "regex", "categoria_id": categoria},
    )
    assert resposta.status_code == 422


def test_categoria_inexistente_ou_de_outro_usuario_e_recusada(
    client_factory, usuario_a: Usuario, usuario_b: Usuario
) -> None:
    """Sem esta checagem uma regra apontaria para a categoria personalizada de outro usuário."""
    cid_b = (
        client_factory(usuario_b).post("/api/categorias", json={"nome": "Pet"}).json()["pluggy_id"]
    )
    client_a = client_factory(usuario_a)
    for categoria_id in ("99999999", cid_b):
        resposta = client_a.post(
            "/api/regras-categorizacao",
            json={"texto": "netflix", "tipo_match": "exato", "categoria_id": categoria_id},
        )
        assert resposta.status_code == 422, categoria_id


def test_categoria_desativada_e_recusada(
    client_factory, usuario_a: Usuario, categoria: str
) -> None:
    client = client_factory(usuario_a)
    client.patch(f"/api/categorias/{categoria}", json={"ativa": False})
    resposta = client.post(
        "/api/regras-categorizacao",
        json={"texto": "netflix", "tipo_match": "exato", "categoria_id": categoria},
    )
    assert resposta.status_code == 422


def test_teto_de_regras(client_factory, db: Session, usuario_a: Usuario, categoria: str) -> None:
    """O casamento "contém" é O(transações × regras) — o teto é o que mantém isso previsível."""
    from app.models.categoria import RegraCategorizacao

    for i in range(MAX_REGRAS):
        db.add(
            RegraCategorizacao(
                usuario_id=usuario_a.id,
                texto=f"regra {i}",
                texto_normalizado=f"regra {i}",
                tipo_match="exato",
                categoria_id=categoria,
            )
        )
    db.commit()

    resposta = client_factory(usuario_a).post(
        "/api/regras-categorizacao",
        json={"texto": "mais uma", "tipo_match": "exato", "categoria_id": categoria},
    )
    assert resposta.status_code == 422
    assert str(MAX_REGRAS) in resposta.json()["detail"]


# --- aplicação às transações ----------------------------------------------------------------


def _transacao(db: Session, usuario: Usuario, conta_id: int, **campos) -> Transacao:
    padrao = {
        "usuario_id": usuario.id,
        "conta_id": conta_id,
        "pluggy_transaction_id": f"tx-{usuario.id}-{campos.get('description', '')}",
        "date": datetime(2026, 3, 10, tzinfo=UTC),
        "amount_centavos": -5000,
        "currency_code": "BRL",
        "type": "DEBIT",
        "status": "POSTED",
    }
    obj = Transacao(**{**padrao, **campos})
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def test_criar_regra_recategoriza_o_historico_e_remover_limpa(
    client_factory, db: Session, usuario_a: Usuario, categoria: str
) -> None:
    conta = criar_conta(db, usuario_a.id, "acc-a")
    tx = _transacao(db, usuario_a, conta.id, description="UBER *TRIP 991")
    assert tx.categoria_regra_id is None

    client = client_factory(usuario_a)
    criada = client.post(
        "/api/regras-categorizacao",
        json={"texto": "uber", "tipo_match": "contem", "categoria_id": categoria},
    )
    assert criada.status_code == 201
    db.refresh(tx)
    assert tx.categoria_regra_id == categoria  # aplicou retroativamente, sem esperar o sync

    assert client.delete(f"/api/regras-categorizacao/{criada.json()['id']}").status_code == 204
    db.refresh(tx)
    assert tx.categoria_regra_id is None  # a coluna pertence às regras


def test_editar_regra_reaplica(
    client_factory, db: Session, usuario_a: Usuario, categoria: str
) -> None:
    db.add(Categoria(pluggy_id="03000000", description="Transport"))
    db.commit()
    conta = criar_conta(db, usuario_a.id, "acc-a")
    tx = _transacao(db, usuario_a, conta.id, description="UBER *TRIP 991")

    client = client_factory(usuario_a)
    regra_id = client.post(
        "/api/regras-categorizacao",
        json={"texto": "uber", "tipo_match": "contem", "categoria_id": categoria},
    ).json()["id"]
    client.patch(f"/api/regras-categorizacao/{regra_id}", json={"categoria_id": "03000000"})
    db.refresh(tx)
    assert tx.categoria_regra_id == "03000000"


def test_aplicacao_nao_atravessa_usuario(
    db: Session, usuario_a: Usuario, usuario_b: Usuario, categoria: str
) -> None:
    from app.models.categoria import RegraCategorizacao

    conta_b = criar_conta(db, usuario_b.id, "acc-b")
    tx_b = _transacao(db, usuario_b, conta_b.id, description="UBER *TRIP 991")

    db.add(
        RegraCategorizacao(
            usuario_id=usuario_a.id,
            texto="uber",
            texto_normalizado="uber",
            tipo_match="contem",
            categoria_id=categoria,
        )
    )
    db.commit()
    aplicar_regras_categorizacao(db, usuario_a.id)

    db.refresh(tx_b)
    assert tx_b.categoria_regra_id is None


def test_aplicacao_e_idempotente(db: Session, usuario_a: Usuario, categoria: str) -> None:
    from app.models.categoria import RegraCategorizacao

    conta = criar_conta(db, usuario_a.id, "acc-a")
    _transacao(db, usuario_a, conta.id, description="UBER *TRIP 991")
    db.add(
        RegraCategorizacao(
            usuario_id=usuario_a.id,
            texto="uber",
            texto_normalizado="uber",
            tipo_match="contem",
            categoria_id=categoria,
        )
    )
    db.commit()

    assert aplicar_regras_categorizacao(db, usuario_a.id) == 1
    assert aplicar_regras_categorizacao(db, usuario_a.id) == 0  # nada mudou na segunda passada
