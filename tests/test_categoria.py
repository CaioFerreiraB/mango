"""Categoria (§4.5): taxonomia global do Pluggy + personalizadas do usuário.

A tabela deixou de ser puramente global — estes testes fixam as duas metades do invariante:
a taxonomia do Pluggy continua compartilhada, e a categoria criada por A é invisível/intocável
para B.
"""

from sqlalchemy.orm import Session

from app.models.categoria import Categoria
from app.models.orcamento import Orcamento
from app.models.usuario import Usuario


def _semear_global(db: Session) -> None:
    db.add(Categoria(pluggy_id="01000000", description="Income", description_translated="Renda"))
    db.add(
        Categoria(pluggy_id="02000000", description="Food", description_translated="Alimentação")
    )
    db.add(
        Categoria(
            pluggy_id="02010000",
            description="Delivery",
            description_translated="Delivery",
            parent_id="02000000",
        )
    )
    db.commit()


# --- taxonomia global ---------------------------------------------------------------------


def test_taxonomia_do_pluggy_e_compartilhada(
    client_factory, db: Session, usuario_a: Usuario, usuario_b: Usuario
) -> None:
    _semear_global(db)
    for user in (usuario_a, usuario_b):
        client = client_factory(user)
        listagem = client.get("/api/categorias").json()
        renda = next(c for c in listagem if c["pluggy_id"] == "01000000")
        assert renda["description_translated"] == "Renda"
        assert renda["personalizada"] is False
        assert renda["ativa"] is True


def test_nao_renomeia_nem_exclui_categoria_do_pluggy(
    client_factory, db: Session, usuario_a: Usuario
) -> None:
    _semear_global(db)
    client = client_factory(usuario_a)
    # Renomear é escrita numa linha compartilhada → recusado (422, regra de negócio).
    assert client.patch("/api/categorias/01000000", json={"nome": "Meu nome"}).status_code == 422
    # Excluir só vale para personalizada → 404 (não confirma sequer que existe).
    assert client.delete("/api/categorias/01000000").status_code == 404
    assert db.get(Categoria, "01000000") is not None


# --- categorias personalizadas ------------------------------------------------------------


def test_cria_renomeia_e_exclui_personalizada(
    client_factory, db: Session, usuario_a: Usuario
) -> None:
    client = client_factory(usuario_a)
    criada = client.post("/api/categorias", json={"nome": "Pet"})
    assert criada.status_code == 201, criada.text
    corpo = criada.json()
    # Id não-numérico de propósito: `transferencia.py` e o ícone do frontend leem prefixo de id.
    assert corpo["pluggy_id"].startswith("u")
    assert not corpo["pluggy_id"][0].isdigit()
    assert corpo["personalizada"] is True and corpo["ativa"] is True
    assert "usuario_id" not in corpo  # o id do dono não vaza na API

    cid = corpo["pluggy_id"]
    assert client.patch(f"/api/categorias/{cid}", json={"nome": "Pets"}).json()["description"] == (
        "Pets"
    )
    assert client.delete(f"/api/categorias/{cid}").status_code == 204
    assert client.get(f"/api/categorias/{cid}").status_code == 404


# --- ícone da categoria personalizada -----------------------------------------------------


def test_icone_e_gravado_na_criacao_e_alteravel(client_factory, usuario_a: Usuario) -> None:
    client = client_factory(usuario_a)
    criada = client.post("/api/categorias", json={"nome": "Pet", "icone": "paw-print"})
    assert criada.status_code == 201, criada.text
    assert criada.json()["icone"] == "paw-print"

    cid = criada.json()["pluggy_id"]
    assert client.patch(f"/api/categorias/{cid}", json={"icone": "dog"}).status_code == 422
    assert client.patch(f"/api/categorias/{cid}", json={"icone": "gift"}).json()["icone"] == "gift"
    listada = next(c for c in client.get("/api/categorias").json() if c["pluggy_id"] == cid)
    assert listada["icone"] == "gift"


def test_icone_e_opcional_e_fora_da_allowlist_e_recusado(
    client_factory, usuario_a: Usuario
) -> None:
    """Allowlist na fronteira (S4): o nome vira componente no cliente, não pode ser texto livre."""
    client = client_factory(usuario_a)
    assert client.post("/api/categorias", json={"nome": "Sem ícone"}).json()["icone"] is None

    # O nome tem de ser VÁLIDO, senão o 422 viria de `NOME_MIN` e a asserção não diria nada sobre
    # o ícone — o par abaixo isola a allowlist: mesmo nome, muda só o ícone.
    recusada = client.post("/api/categorias", json={"nome": "Com ícone", "icone": "<script>"})
    assert recusada.status_code == 422
    aceita = client.post("/api/categorias", json={"nome": "Com ícone", "icone": "gift"})
    assert aceita.status_code == 201, aceita.text


def test_icone_da_categoria_do_pluggy_e_recusado(
    client_factory, db: Session, usuario_a: Usuario
) -> None:
    """A linha é compartilhada entre usuários — lá o ícone vem da raiz do id, igual para todos."""
    _semear_global(db)
    client = client_factory(usuario_a)
    assert client.patch("/api/categorias/01000000", json={"icone": "gift"}).status_code == 422
    assert db.get(Categoria, "01000000").icone is None


def test_nome_duplicado_ignora_caixa_e_acento(client_factory, usuario_a: Usuario) -> None:
    client = client_factory(usuario_a)
    assert client.post("/api/categorias", json={"nome": "Farmácia"}).status_code == 201
    assert client.post("/api/categorias", json={"nome": "farmacia"}).status_code == 409
    assert client.post("/api/categorias", json={"nome": "  FARMÁCIA  "}).status_code == 409
    # Nome distinto passa.
    assert client.post("/api/categorias", json={"nome": "Farmácia veterinária"}).status_code == 201


def test_nome_curto_demais_e_recusado(client_factory, usuario_a: Usuario) -> None:
    client = client_factory(usuario_a)
    assert client.post("/api/categorias", json={"nome": "a"}).status_code == 422
    assert client.post("/api/categorias", json={"nome": "  "}).status_code == 422


def test_exclusao_bloqueada_quando_ha_orcamento(
    client_factory, db: Session, usuario_a: Usuario
) -> None:
    """Sem a pré-checagem isto seria IntegrityError (500): `orcamento.categoria_id` é NOT NULL
    com ondelete=RESTRICT."""
    client = client_factory(usuario_a)
    cid = client.post("/api/categorias", json={"nome": "Pet"}).json()["pluggy_id"]
    db.add(
        Orcamento(
            usuario_id=usuario_a.id,
            categoria_id=cid,
            tipo="despesa",
            limite_padrao_centavos=10000,
            ordem=1,
        )
    )
    db.commit()

    resposta = client.delete(f"/api/categorias/{cid}")
    assert resposta.status_code == 409
    assert "orçamento" in resposta.json()["detail"]
    assert db.get(Categoria, cid) is not None


# --- isolamento (S3) ----------------------------------------------------------------------


def test_personalizada_de_a_e_invisivel_e_intocavel_para_b(
    client_factory, usuario_a: Usuario, usuario_b: Usuario
) -> None:
    client_a = client_factory(usuario_a)
    cid = client_a.post("/api/categorias", json={"nome": "Pet"}).json()["pluggy_id"]

    client_b = client_factory(usuario_b)
    assert all(c["pluggy_id"] != cid for c in client_b.get("/api/categorias").json())
    assert client_b.get(f"/api/categorias/{cid}").status_code == 404
    assert client_b.patch(f"/api/categorias/{cid}", json={"nome": "Roubada"}).status_code == 404
    assert client_b.delete(f"/api/categorias/{cid}").status_code == 404

    # B pode ter uma categoria com o MESMO nome — a unicidade é por usuário.
    assert client_b.post("/api/categorias", json={"nome": "Pet"}).status_code == 201
    assert client_a.get(f"/api/categorias/{cid}").json()["description"] == "Pet"


# --- ativação -----------------------------------------------------------------------------


def test_ativacao_e_por_usuario_e_alcanca_a_subarvore(
    client_factory, db: Session, usuario_a: Usuario, usuario_b: Usuario
) -> None:
    _semear_global(db)
    client_a = client_factory(usuario_a)
    assert client_a.patch("/api/categorias/02000000", json={"ativa": False}).status_code == 200

    estado_a = {c["pluggy_id"]: c["ativa"] for c in client_a.get("/api/categorias").json()}
    assert estado_a["02000000"] is False
    assert estado_a["02010000"] is False  # a filha foi junto
    assert estado_a["01000000"] is True  # irmã intocada

    # B não é afetado: o estado é por usuário.
    estado_b = {
        c["pluggy_id"]: c["ativa"] for c in client_factory(usuario_b).get("/api/categorias").json()
    }
    assert estado_b["02000000"] is True and estado_b["02010000"] is True

    # `apenas_ativas` filtra no servidor.
    ativas = client_a.get("/api/categorias", params={"apenas_ativas": True}).json()
    assert all(c["pluggy_id"] not in ("02000000", "02010000") for c in ativas)

    # Reativar também alcança a subárvore, e é idempotente.
    assert client_a.patch("/api/categorias/02000000", json={"ativa": True}).status_code == 200
    assert client_a.patch("/api/categorias/02000000", json={"ativa": True}).status_code == 200
    estado_a = {c["pluggy_id"]: c["ativa"] for c in client_a.get("/api/categorias").json()}
    assert estado_a["02000000"] is True and estado_a["02010000"] is True
