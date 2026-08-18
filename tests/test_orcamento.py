"""Regra #20 (soma das subcategorias ≤ orçamento da categoria) + unicidade por categoria+tipo,
materialização mensal e consumo/alertas (§4.6), com suporte a despesa e receita."""

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
from app.services.periodo import hoje_sp
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


def test_soma_subcategorias_respeita_teto(client_factory, db: Session, usuario_a: Usuario) -> None:
    _semear_categorias(db)
    client = client_factory(usuario_a)

    # Orçamento do pai = 1000; um filho com 600 cabe.
    assert (
        client.post(
            "/api/orcamentos",
            json={"categoria_id": PAI, "tipo": "despesa", "limite_padrao_centavos": 1000},
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/orcamentos",
            json={"categoria_id": FILHO_1, "tipo": "despesa", "limite_padrao_centavos": 600},
        ).status_code
        == 201
    )

    # Segundo filho com 500 → 600+500=1100 > 1000 → 422 (#20).
    resp = client.post(
        "/api/orcamentos",
        json={"categoria_id": FILHO_2, "tipo": "despesa", "limite_padrao_centavos": 500},
    )
    assert resp.status_code == 422

    # Com 400 → 600+400=1000 ≤ 1000 → OK.
    assert (
        client.post(
            "/api/orcamentos",
            json={"categoria_id": FILHO_2, "tipo": "despesa", "limite_padrao_centavos": 400},
        ).status_code
        == 201
    )


def test_regra_20_nao_vaza_entre_tipos(client_factory, db: Session, usuario_a: Usuario) -> None:
    """Uma receita no pai e uma despesa no filho não devem interagir na regra #20."""
    _semear_categorias(db)
    client = client_factory(usuario_a)

    assert (
        client.post(
            "/api/orcamentos",
            json={"categoria_id": PAI, "tipo": "receita", "limite_padrao_centavos": 100},
        ).status_code
        == 201
    )
    # Despesa no filho, bem acima do teto (inexistente) de despesa do pai — não deve estourar
    # a regra #20, já que o orçamento do pai é de receita, não de despesa.
    assert (
        client.post(
            "/api/orcamentos",
            json={"categoria_id": FILHO_1, "tipo": "despesa", "limite_padrao_centavos": 999_999},
        ).status_code
        == 201
    )


def test_orcamento_unico_por_categoria_e_tipo(
    client_factory, db: Session, usuario_a: Usuario
) -> None:
    _semear_categorias(db)
    client = client_factory(usuario_a)
    assert (
        client.post(
            "/api/orcamentos",
            json={"categoria_id": FILHO_1, "tipo": "despesa", "limite_padrao_centavos": 100},
        ).status_code
        == 201
    )
    # Duplicado (mesma categoria, mesmo tipo) → 409.
    resp = client.post(
        "/api/orcamentos",
        json={"categoria_id": FILHO_1, "tipo": "despesa", "limite_padrao_centavos": 200},
    )
    assert resp.status_code == 409
    # Mesma categoria, tipo diferente → permitido (é um orçamento independente).
    assert (
        client.post(
            "/api/orcamentos",
            json={"categoria_id": FILHO_1, "tipo": "receita", "limite_padrao_centavos": 300},
        ).status_code
        == 201
    )


def _linhas_mensais(db: Session, usuario_id: int) -> list[OrcamentoMensal]:
    return list(
        db.scalars(select(OrcamentoMensal).where(OrcamentoMensal.usuario_id == usuario_id)).all()
    )


def test_materializacao_mensal_idempotente(db: Session, usuario_a: Usuario) -> None:
    _semear_categorias(db)
    OrcamentoRepository(db, usuario_a.id).create(
        categoria_id=PAI, tipo="despesa", limite_padrao_centavos=1000, ordem=0
    )

    assert materializar_mes(db, usuario_a.id, 2026, 6) == 1
    assert materializar_mes(db, usuario_a.id, 2026, 6) == 0  # não duplica

    (linha,) = _linhas_mensais(db, usuario_a.id)
    assert linha.limite_centavos == 1000 and linha.editado_manualmente is False


def test_materializacao_carrega_tipo(db: Session, usuario_a: Usuario) -> None:
    _semear_categorias(db)
    OrcamentoRepository(db, usuario_a.id).create(
        categoria_id=PAI, tipo="receita", limite_padrao_centavos=2000, ordem=0
    )
    materializar_mes(db, usuario_a.id, 2026, 6)
    (linha,) = _linhas_mensais(db, usuario_a.id)
    assert linha.tipo == "receita"


def test_materializacao_preserva_edicao_manual(db: Session, usuario_a: Usuario) -> None:
    _semear_categorias(db)
    OrcamentoRepository(db, usuario_a.id).create(
        categoria_id=PAI, tipo="despesa", limite_padrao_centavos=1000, ordem=0
    )
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
        categoria_id=PAI, tipo="despesa", limite_padrao_centavos=1000, recorrente=False, ordem=0
    )
    assert materializar_mes(db, usuario_a.id, 2026, 6) == 0


def test_consumo_gasto_subarvore_alerta_e_transferencia(db: Session, usuario_a: Usuario) -> None:
    _semear_categorias(db)
    OrcamentoRepository(db, usuario_a.id).create(
        categoria_id=PAI, tipo="despesa", limite_padrao_centavos=100_000, ordem=0
    )
    conta = criar_conta(db, usuario_a.id, "acc-consumo")

    # Gasto lançado nos FILHOS conta para o orçamento do PAI (subárvore, §4.6/#20).
    _tx(db, usuario_a.id, conta, "t1", -60_000, FILHO_1)
    _tx(db, usuario_a.id, conta, "t2", -30_000, FILHO_2)
    # Transferência não entra no gasto (§4.2).
    _tx(db, usuario_a.id, conta, "t3", -50_000, FILHO_1, eh=True)

    # Materializa explicitamente: `consumo_do_mes` só materializa sob demanda pro mês
    # corrente de verdade, e 2026-06 (data fixa das transações de teste) pode não ser o mês
    # corrente real — o teste de materialização automática é separado (ver abaixo).
    materializar_mes(db, usuario_a.id, 2026, 6)

    consumo = consumo_do_mes(db, usuario_a.id, 2026, 6)
    (item,) = consumo.itens
    assert item.categoria_id == PAI
    assert item.realizado_centavos == 90_000  # 60k + 30k, sem a transferência
    assert item.percentual == 90
    assert item.alerta_atingido == 90


def test_consumo_receita_sem_alerta(db: Session, usuario_a: Usuario) -> None:
    _semear_categorias(db)
    OrcamentoRepository(db, usuario_a.id).create(
        categoria_id=PAI, tipo="receita", limite_padrao_centavos=10_000, ordem=0
    )
    conta = criar_conta(db, usuario_a.id, "acc-receita")
    _tx(db, usuario_a.id, conta, "t1", 15_000, FILHO_1)  # recebido > meta (150%)

    materializar_mes(db, usuario_a.id, 2026, 6)
    consumo = consumo_do_mes(db, usuario_a.id, 2026, 6)
    (item,) = consumo.itens
    assert item.tipo == "receita"
    assert item.realizado_centavos == 15_000
    assert item.percentual == 150
    assert item.alerta_atingido is None  # receita nunca "alerta", mesmo passando da meta


def test_consumo_gasto_sempre_positivo_mesmo_com_debit_armazenado_positivo(
    db: Session, usuario_a: Usuario
) -> None:
    """O sinal de `amount_centavos` numa transação DEBIT nem sempre é negativo na prática
    (varia conforme a origem dos dados) — `realizado_centavos` tem que sair sempre em módulo,
    nunca negativo, independente de como o valor foi armazenado."""
    _semear_categorias(db)
    OrcamentoRepository(db, usuario_a.id).create(
        categoria_id=PAI, tipo="despesa", limite_padrao_centavos=10_000, ordem=0
    )
    conta = criar_conta(db, usuario_a.id, "acc-sinal")
    # DEBIT com amount_centavos POSITIVO (ao contrário da convenção usual) — `_tx` sempre monta
    # negativo pra DEBIT, então insere direto pelo repositório aqui.
    TransacaoRepository(db, usuario_a.id).create(
        conta_id=conta.id,
        pluggy_transaction_id="t-sinal",
        date=datetime(2026, 6, 15, 12, tzinfo=UTC),
        amount_centavos=9_069,
        currency_code="BRL",
        type="DEBIT",
        status="POSTED",
        categoria_pluggy_id=FILHO_1,
        eh_transferencia=False,
    )

    materializar_mes(db, usuario_a.id, 2026, 6)
    consumo = consumo_do_mes(db, usuario_a.id, 2026, 6)
    (item,) = consumo.itens
    assert item.realizado_centavos == 9_069
    assert item.percentual == round(9_069 / 10_000 * 100)


def test_consumo_nao_materializa_mes_passado_sem_dados(db: Session, usuario_a: Usuario) -> None:
    """Um mês nunca antes materializado, estritamente anterior ao mês corrente, deve ficar
    vazio — nunca ganhar orçamento retroativo baseado no padrão de hoje."""
    _semear_categorias(db)
    OrcamentoRepository(db, usuario_a.id).create(
        categoria_id=PAI, tipo="despesa", limite_padrao_centavos=1000, ordem=0
    )

    consumo = consumo_do_mes(db, usuario_a.id, 2019, 3)  # bem no passado, nunca visitado
    assert consumo.itens == []
    assert _linhas_mensais(db, usuario_a.id) == []  # nada foi criado como efeito colateral


def test_consumo_materializa_mes_corrente(db: Session, usuario_a: Usuario) -> None:
    _semear_categorias(db)
    OrcamentoRepository(db, usuario_a.id).create(
        categoria_id=PAI, tipo="despesa", limite_padrao_centavos=1000, ordem=0
    )

    hoje = hoje_sp()
    consumo = consumo_do_mes(db, usuario_a.id, hoje.year, hoje.month)
    (item,) = consumo.itens
    assert item.categoria_id == PAI
    assert item.limite_centavos == 1000


def test_consumo_ordenado_por_ordem(db: Session, usuario_a: Usuario) -> None:
    """A ordem exibida segue `Orcamento.ordem` (definida no modal padrão), não o percentual."""
    _semear_categorias(db)
    repo = OrcamentoRepository(db, usuario_a.id)
    # FILHO_2 tem ordem 0 (primeiro) mas gasto/percentual bem menor que FILHO_1 (ordem 1).
    repo.create(categoria_id=FILHO_2, tipo="despesa", limite_padrao_centavos=100_000, ordem=0)
    repo.create(categoria_id=FILHO_1, tipo="despesa", limite_padrao_centavos=100, ordem=1)
    conta = criar_conta(db, usuario_a.id, "acc-ordem")
    _tx(db, usuario_a.id, conta, "t1", -100, FILHO_1)  # 100% do FILHO_1

    materializar_mes(db, usuario_a.id, 2026, 6)
    consumo = consumo_do_mes(db, usuario_a.id, 2026, 6)
    assert [item.categoria_id for item in consumo.itens] == [FILHO_2, FILHO_1]


def test_consumo_expoe_recorrente_e_suprimido(db: Session, usuario_a: Usuario) -> None:
    _semear_categorias(db)
    OrcamentoRepository(db, usuario_a.id).create(
        categoria_id=PAI, tipo="despesa", limite_padrao_centavos=1000, ordem=0
    )
    materializar_mes(db, usuario_a.id, 2026, 6)
    consumo = consumo_do_mes(db, usuario_a.id, 2026, 6)
    (item,) = consumo.itens
    assert item.recorrente is True
    assert item.suprimido is False


def test_suprimido_sobrevive_a_remateralizacao(db: Session, usuario_a: Usuario) -> None:
    """Suprimir uma categoria só do mês (via "Editar mês") não pode ser desfeito pela
    materialização automática — a linha continua existindo (só marcada), então o backstop
    não a recria."""
    _semear_categorias(db)
    OrcamentoRepository(db, usuario_a.id).create(
        categoria_id=PAI, tipo="despesa", limite_padrao_centavos=1000, ordem=0
    )
    materializar_mes(db, usuario_a.id, 2026, 6)
    (linha,) = _linhas_mensais(db, usuario_a.id)
    linha.suprimido = True
    db.commit()

    materializar_mes(db, usuario_a.id, 2026, 6)  # não recria, a linha "já existe"
    linhas = _linhas_mensais(db, usuario_a.id)
    assert len(linhas) == 1
    assert linhas[0].suprimido is True

    # O consumo do mês ainda enxerga a linha suprimida (a Visão Geral que filtra) — "Editar
    # mês" precisa dela pra oferecer "restaurar".
    consumo = consumo_do_mes(db, usuario_a.id, 2026, 6)
    (item,) = consumo.itens
    assert item.suprimido is True


def test_materializar_endpoint_aplica_padrao_a_mes_passado(
    client_factory, db: Session, usuario_a: Usuario
) -> None:
    """POST /orcamentos/materializar aplica o padrão sob pedido a um mês específico — inclusive
    um mês passado, que a leitura normal (`GET /orcamentos/consumo`) não materializa sozinha."""
    _semear_categorias(db)
    client = client_factory(usuario_a)
    assert (
        client.post(
            "/api/orcamentos",
            json={"categoria_id": PAI, "tipo": "despesa", "limite_padrao_centavos": 1000},
        ).status_code
        == 201
    )

    # Mês passado, nunca visitado: a leitura normal fica vazia.
    assert client.get("/api/orcamentos/consumo?ano=2019&mes=3").json()["itens"] == []

    # Pedido explícito de materialização: aplica o padrão a esse mês específico.
    resp = client.post("/api/orcamentos/materializar?ano=2019&mes=3")
    assert resp.status_code == 200
    (item,) = resp.json()["itens"]
    assert item["categoria_id"] == PAI
    assert item["limite_centavos"] == 1000

    # Idempotente: chamar de novo não duplica.
    resp2 = client.post("/api/orcamentos/materializar?ano=2019&mes=3")
    assert len(resp2.json()["itens"]) == 1


def test_orcamento_pontual_nao_recorrente_fica_restrito_ao_mes(
    client_factory, db: Session, usuario_a: Usuario
) -> None:
    """Um orçamento pontual (recorrente=False, criado via "Editar mês" pra um mês específico)
    nunca é materializado em outro mês (§4.6) — fica restrito a onde foi criado."""
    _semear_categorias(db)
    client = client_factory(usuario_a)
    oid = client.post(
        "/api/orcamentos",
        json={
            "categoria_id": FILHO_1,
            "tipo": "despesa",
            "limite_padrao_centavos": 500,
            "recorrente": False,
        },
    ).json()["id"]
    assert (
        client.post(
            "/api/orcamentos-mensais",
            json={
                "orcamento_id": oid,
                "categoria_id": FILHO_1,
                "tipo": "despesa",
                "ano": 2019,
                "mes": 3,
                "limite_centavos": 500,
            },
        ).status_code
        == 201
    )

    assert materializar_mes(db, usuario_a.id, 2019, 4) == 0  # não vaza pro mês seguinte
    consumo_marco = consumo_do_mes(db, usuario_a.id, 2019, 3)
    assert len(consumo_marco.itens) == 1


def test_orcamento_isolamento(
    client_factory, db: Session, usuario_a: Usuario, usuario_b: Usuario
) -> None:
    _semear_categorias(db)
    a = client_factory(usuario_a)
    b = client_factory(usuario_b)
    oid = a.post(
        "/api/orcamentos",
        json={"categoria_id": PAI, "tipo": "despesa", "limite_padrao_centavos": 1000},
    ).json()["id"]

    assert b.get("/api/orcamentos").json() == []
    assert b.get(f"/api/orcamentos/{oid}").status_code == 404
    assert b.patch(f"/api/orcamentos/{oid}", json={"limite_padrao_centavos": 5}).status_code == 404
    assert b.delete(f"/api/orcamentos/{oid}").status_code == 404
    assert len(a.get("/api/orcamentos").json()) == 1
