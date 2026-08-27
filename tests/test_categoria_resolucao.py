"""Precedência da categoria efetiva (§4.5) e a PARIDADE entre as duas formas de resolvê-la.

A regra existe duas vezes — expressão SQL (agregações) e função Python (serialização). O teste de
paridade é o que impede as duas de divergirem: qualquer mudança numa sem a outra quebra aqui.
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.assinatura import Assinatura
from app.models.categoria import Categoria, CategoriaDesativada
from app.models.transacao import Transacao
from app.models.usuario import Usuario
from app.services.categoria_resolucao import (
    carregar_contexto,
    com_assinatura,
    expr_categoria_efetiva,
    resolver,
)
from tests.helpers import criar_conta

CAT_ASSINATURA = "01000000"
CAT_MANUAL = "02000000"
CAT_REGRA = "03000000"
CAT_BANCO = "06000000"
CAT_DESATIVADA = "07000000"
TODAS = (CAT_ASSINATURA, CAT_MANUAL, CAT_REGRA, CAT_BANCO, CAT_DESATIVADA)


@pytest.fixture
def cenario(db: Session, usuario_a: Usuario):
    """Uma transação por combinação relevante das quatro fontes de categoria."""
    for cid in TODAS:
        db.add(Categoria(pluggy_id=cid, description=cid))
    db.commit()
    db.add(CategoriaDesativada(usuario_id=usuario_a.id, categoria_id=CAT_DESATIVADA))

    com_categoria = Assinatura(
        usuario_id=usuario_a.id,
        nome="Streaming",
        valor_centavos=2990,
        periodicidade="mensal",
        categoria_id=CAT_ASSINATURA,
        nomes_transacao=[],
    )
    sem_categoria = Assinatura(
        usuario_id=usuario_a.id,
        nome="Sem categoria",
        valor_centavos=1000,
        periodicidade="mensal",
        categoria_id=None,
        nomes_transacao=[],
    )
    db.add_all([com_categoria, sem_categoria])
    db.commit()

    conta = criar_conta(db, usuario_a.id, "acc-a")
    casos = {
        # nome do caso: (assinatura, override, regra, pluggy)
        "so_pluggy": (None, None, None, CAT_BANCO),
        "pluggy_desativada": (None, None, None, CAT_DESATIVADA),
        "sem_nada": (None, None, None, None),
        "so_regra": (None, None, CAT_REGRA, None),
        "regra_vence_pluggy": (None, None, CAT_REGRA, CAT_BANCO),
        "manual_vence_regra": (None, CAT_MANUAL, CAT_REGRA, CAT_BANCO),
        "manual_sobrevive_desativacao": (None, CAT_MANUAL, None, CAT_DESATIVADA),
        "regra_sobrevive_desativacao": (None, None, CAT_REGRA, CAT_DESATIVADA),
        "assinatura_vence_tudo": (com_categoria, CAT_MANUAL, CAT_REGRA, CAT_BANCO),
        "assinatura_sem_categoria_cai_pro_manual": (sem_categoria, CAT_MANUAL, None, CAT_BANCO),
        "assinatura_sem_categoria_cai_pro_pluggy": (sem_categoria, None, None, CAT_BANCO),
    }

    criadas: dict[str, Transacao] = {}
    for nome, (assinatura, override, regra, pluggy) in casos.items():
        tx = Transacao(
            usuario_id=usuario_a.id,
            conta_id=conta.id,
            pluggy_transaction_id=f"tx-{nome}",
            date=datetime(2026, 3, 10, tzinfo=UTC),
            amount_centavos=-5000,
            currency_code="BRL",
            type="DEBIT",
            status="POSTED",
            assinatura_id=assinatura.id if assinatura else None,
            categoria_override_id=override,
            categoria_regra_id=regra,
            categoria_pluggy_id=pluggy,
        )
        db.add(tx)
        criadas[nome] = tx
    db.commit()
    return criadas


@pytest.mark.parametrize(
    "caso,esperado,origem",
    [
        ("so_pluggy", CAT_BANCO, "banco"),
        ("pluggy_desativada", None, "desconhecida"),
        ("sem_nada", None, "desconhecida"),
        ("so_regra", CAT_REGRA, "regra"),
        ("regra_vence_pluggy", CAT_REGRA, "regra"),
        ("manual_vence_regra", CAT_MANUAL, "manual"),
        ("manual_sobrevive_desativacao", CAT_MANUAL, "manual"),
        ("regra_sobrevive_desativacao", CAT_REGRA, "regra"),
        ("assinatura_vence_tudo", CAT_ASSINATURA, "assinatura"),
        ("assinatura_sem_categoria_cai_pro_manual", CAT_MANUAL, "manual"),
        ("assinatura_sem_categoria_cai_pro_pluggy", CAT_BANCO, "banco"),
    ],
)
def test_precedencia(
    db: Session, usuario_a: Usuario, cenario, caso: str, esperado: str | None, origem: str
) -> None:
    ctx = carregar_contexto(db, usuario_a.id)
    assert resolver(cenario[caso], ctx) == (esperado, origem)


def test_paridade_sql_e_python(db: Session, usuario_a: Usuario, cenario) -> None:
    """As duas formas têm de concordar em TODA a matriz — é o contrato entre elas."""
    ctx = carregar_contexto(db, usuario_a.id)
    por_python = {tx.id: resolver(tx, ctx)[0] for tx in cenario.values()}

    linhas = db.execute(
        com_assinatura(
            select(Transacao.id, expr_categoria_efetiva(usuario_a.id)), usuario_a.id
        ).where(Transacao.usuario_id == usuario_a.id)
    ).all()
    assert dict(linhas) == por_python


def test_desativacao_de_um_usuario_nao_afeta_o_outro(
    db: Session, usuario_a: Usuario, usuario_b: Usuario, cenario
) -> None:
    """A expressão é parametrizada por usuário: a mesma linha resolve diferente para cada um."""
    tx = cenario["pluggy_desativada"]

    def efetiva(usuario_id: int) -> str | None:
        linha = db.execute(
            com_assinatura(
                select(Transacao.id, expr_categoria_efetiva(usuario_id)), usuario_id
            ).where(Transacao.id == tx.id)
        ).one()
        return linha[1]

    para_a, para_b = efetiva(usuario_a.id), efetiva(usuario_b.id)
    assert para_a is None  # A desativou → desconhecida
    assert para_b == CAT_DESATIVADA  # B não desativou → continua valendo


def test_contexto_nao_vaza_entre_usuarios(db: Session, usuario_b: Usuario, cenario) -> None:
    ctx_b = carregar_contexto(db, usuario_b.id)
    assert ctx_b.categorias_de_assinatura == {}
    assert ctx_b.desativadas == frozenset()
