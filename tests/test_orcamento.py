"""Regra #20 (soma das subcategorias ≤ orçamento da categoria) + unicidade por categoria,
materialização mensal e consumo/alertas (§4.6)."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.categoria import Categoria
from app.models.orcamento import OrcamentoMensal
from app.models.usuario import Usuario
from app.repositories.orcamento import OrcamentoRepository
from app.repositories.transacao import TransacaoRepository
from app.services.orcamento_consumo import consumo_do_mes
from app.services.orcamento_mensal import materializar_mes
from tests.helpers import criar_conta

PAI = "10000000"
FILHO_1 = "10010000"
FILHO_2 = "10020000"


def _tx(db: Session, usuario_id: int, conta, pid: str, valor: int, cat: str, eh: bool = False):
    """Transação em 15/06/2026 12:00 UTC (09:00 SP → mesmo dia civil)."""
    return TransacaoRepository(db, usuario_id).create(
        conta_id=conta.id,
        pluggy_transaction_id=pid,
        date=datetime(2026, 6, 15, 12, tzinfo=UTC),
        amount_centavos=valor,
        currency_code="BRL",
        type="CREDIT" if valor > 0 else "DEBIT",
        status="POSTED",
        categoria_pluggy_id=cat,
        eh_transferencia=eh,
    )


def _semear_categorias(db: Session) -> None:
    db.add(Categoria(pluggy_id=PAI, description="Pai"))
    db.flush()
    db.add(Categoria(pluggy_id=FILHO_1, description="Filho 1", parent_id=PAI))
    db.add(Categoria(pluggy_id=FILHO_2, description="Filho 2", parent_id=PAI))
    db.commit()


def test_soma_subcategorias_respeita_teto(
    client_factory, db: Session, usuario_a: Usuario
) -> None:
    _semear_categorias(db)
    client = client_factory(usuario_a)

    # Orçamento do pai = 1000; um filho com 600 cabe.
    assert client.post(
        "/api/orcamentos", json={"categoria_id": PAI, "limite_padrao_centavos": 1000}
    ).status_code == 201
    assert client.post(
        "/api/orcamentos", json={"categoria_id": FILHO_1, "limite_padrao_centavos": 600}
    ).status_code == 201

    # Segundo filho com 500 → 600+500=1100 > 1000 → 422 (#20).
    resp = client.post(
        "/api/orcamentos", json={"categoria_id": FILHO_2, "limite_padrao_centavos": 500}
    )
    assert resp.status_code == 422

    # Com 400 → 600+400=1000 ≤ 1000 → OK.
    assert client.post(
        "/api/orcamentos", json={"categoria_id": FILHO_2, "limite_padrao_centavos": 400}
    ).status_code == 201


def test_orcamento_unico_por_categoria(
    client_factory, db: Session, usuario_a: Usuario
) -> None:
    _semear_categorias(db)
    client = client_factory(usuario_a)
    assert client.post(
        "/api/orcamentos", json={"categoria_id": FILHO_1, "limite_padrao_centavos": 100}
    ).status_code == 201
    # Duplicado → 409.
    resp = client.post(
        "/api/orcamentos", json={"categoria_id": FILHO_1, "limite_padrao_centavos": 200}
    )
    assert resp.status_code == 409


def _linhas_mensais(db: Session, usuario_id: int) -> list[OrcamentoMensal]:
    return list(
        db.scalars(
            select(OrcamentoMensal).where(OrcamentoMensal.usuario_id == usuario_id)
        ).all()
    )


def test_materializacao_mensal_idempotente(db: Session, usuario_a: Usuario) -> None:
    _semear_categorias(db)
    OrcamentoRepository(db, usuario_a.id).create(categoria_id=PAI, limite_padrao_centavos=1000)

    assert materializar_mes(db, usuario_a.id, 2026, 6) == 1
    assert materializar_mes(db, usuario_a.id, 2026, 6) == 0  # não duplica

    (linha,) = _linhas_mensais(db, usuario_a.id)
    assert linha.limite_centavos == 1000 and linha.editado_manualmente is False


def test_materializacao_preserva_edicao_manual(db: Session, usuario_a: Usuario) -> None:
    _semear_categorias(db)
    OrcamentoRepository(db, usuario_a.id).create(categoria_id=PAI, limite_padrao_centavos=1000)
    materializar_mes(db, usuario_a.id, 2026, 6)

    (linha,) = _linhas_mensais(db, usuario_a.id)
    linha.limite_centavos = 5000
    linha.editado_manualmente = True
    db.commit()

    materializar_mes(db, usuario_a.id, 2026, 6)  # não sobrescreve o limite editado
    db.refresh(linha)
    assert linha.limite_centavos == 5000


def test_nao_materializa_orcamento_nao_recorrente(db: Session, usuario_a: Usuario) -> None:
    _semear_categorias(db)
    OrcamentoRepository(db, usuario_a.id).create(
        categoria_id=PAI, limite_padrao_centavos=1000, recorrente=False
    )
    assert materializar_mes(db, usuario_a.id, 2026, 6) == 0


def test_consumo_gasto_subarvore_alerta_e_transferencia(
    db: Session, usuario_a: Usuario
) -> None:
    _semear_categorias(db)
    OrcamentoRepository(db, usuario_a.id).create(categoria_id=PAI, limite_padrao_centavos=100_000)
    conta = criar_conta(db, usuario_a.id, "acc-consumo")

    # Gasto lançado nos FILHOS conta para o orçamento do PAI (subárvore, §4.6/#20).
    _tx(db, usuario_a.id, conta, "t1", -60_000, FILHO_1)
    _tx(db, usuario_a.id, conta, "t2", -30_000, FILHO_2)
    # Transferência não entra no gasto (§4.2).
    _tx(db, usuario_a.id, conta, "t3", -50_000, FILHO_1, eh=True)

    consumo = consumo_do_mes(db, usuario_a.id, 2026, 6)
    (item,) = consumo.itens
    assert item.categoria_id == PAI
    assert item.gasto_centavos == 90_000  # 60k + 30k, sem a transferência
    assert item.percentual == 90
    assert item.alerta_atingido == 90


def test_orcamento_isolamento(
    client_factory, db: Session, usuario_a: Usuario, usuario_b: Usuario
) -> None:
    _semear_categorias(db)
    a = client_factory(usuario_a)
    b = client_factory(usuario_b)
    oid = a.post(
        "/api/orcamentos", json={"categoria_id": PAI, "limite_padrao_centavos": 1000}
    ).json()["id"]

    assert b.get("/api/orcamentos").json() == []
    assert b.get(f"/api/orcamentos/{oid}").status_code == 404
    assert b.patch(f"/api/orcamentos/{oid}", json={"limite_padrao_centavos": 5}).status_code == 404
    assert b.delete(f"/api/orcamentos/{oid}").status_code == 404
    assert len(a.get("/api/orcamentos").json()) == 1
