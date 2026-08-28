"""Parcelas da mesma compra dividem a categoria (§4.5).

O Pluggy não expõe id de compra, então o agrupamento é heurístico — estes testes fixam tanto o que
DEVE agrupar quanto o que NÃO pode agrupar (o risco real é recategorizar transação alheia à compra).
"""

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from app.models.assinatura import Assinatura
from app.models.categoria import Categoria
from app.models.transacao import Transacao
from app.models.usuario import Usuario
from app.services.compra_parcelada import chave_compra
from tests.helpers import criar_conta

# --- chave (pura) ---------------------------------------------------------------------------


@dataclass
class TxFalsa:
    conta_id: int = 1
    date: datetime = datetime(2026, 3, 10, tzinfo=UTC)
    description: str | None = "LOJA X"
    merchant_cnpj: str | None = None
    merchant_nome: str | None = None
    installment_number: int | None = 1
    total_installments: int | None = 3
    total_amount_centavos: int | None = 30000


def test_transacao_nao_parcelada_nao_tem_chave() -> None:
    assert chave_compra(TxFalsa(total_installments=None)) is None
    assert chave_compra(TxFalsa(total_installments=1)) is None


def test_parcelas_da_mesma_compra_tem_a_mesma_chave() -> None:
    """A âncora desfaz o deslocamento mensal: 1/3 em jan, 2/3 em fev e 3/3 em mar são uma compra."""
    jan = TxFalsa(date=datetime(2026, 1, 10, tzinfo=UTC), installment_number=1)
    fev = TxFalsa(date=datetime(2026, 2, 10, tzinfo=UTC), installment_number=2)
    mar = TxFalsa(date=datetime(2026, 3, 10, tzinfo=UTC), installment_number=3)
    assert chave_compra(jan) == chave_compra(fev) == chave_compra(mar)


def test_compras_identicas_em_meses_diferentes_nao_se_misturam() -> None:
    """Sem a âncora de mês estas duas cairiam no mesmo grupo — é o caso que ela evita."""
    compra_jan = TxFalsa(date=datetime(2026, 1, 10, tzinfo=UTC), installment_number=1)
    compra_mai = TxFalsa(date=datetime(2026, 5, 10, tzinfo=UTC), installment_number=1)
    assert chave_compra(compra_jan) != chave_compra(compra_mai)


def test_ancora_atravessa_a_virada_de_ano() -> None:
    dez = TxFalsa(date=datetime(2025, 12, 10, tzinfo=UTC), installment_number=1)
    jan = TxFalsa(date=datetime(2026, 1, 10, tzinfo=UTC), installment_number=2)
    assert chave_compra(dez) == chave_compra(jan)


def test_chave_separa_por_conta_valor_e_numero_de_parcelas() -> None:
    base = TxFalsa()
    assert chave_compra(base) != chave_compra(TxFalsa(conta_id=2))
    assert chave_compra(base) != chave_compra(TxFalsa(total_amount_centavos=40000))
    assert chave_compra(base) != chave_compra(TxFalsa(total_installments=4))


def test_cnpj_tem_precedencia_sobre_o_nome() -> None:
    """O nome do estabelecimento varia entre lançamentos; o CNPJ não."""
    a = TxFalsa(merchant_cnpj="123", description="LOJA X *01")
    b = TxFalsa(merchant_cnpj="123", description="LOJA X *02")
    assert chave_compra(a) == chave_compra(b)


def test_nome_normalizado_ignora_caixa_e_acento() -> None:
    a = TxFalsa(description="MERCEARIA SÃO JOÃO")
    b = TxFalsa(description="mercearia sao joao")
    assert chave_compra(a) == chave_compra(b)


def test_sem_estabelecimento_nao_agrupa() -> None:
    """Melhor não agrupar do que agrupar errado: sem nome nem CNPJ não há como identificar."""
    assert chave_compra(TxFalsa(description=None, merchant_nome=None)) is None


# --- descrição real do cartão (regressão) ---------------------------------------------------
#
# O caso que quebrava na prática: a Pluggy manda `merchant_nome`, `merchant_cnpj` e
# `total_amount_centavos` VAZIOS, e o único identificador é a descrição — que carrega o contador
# de parcela ("1/6") e às vezes muda de forma no meio da compra. Sem tirar esses dois pedaços,
# cada parcela ganhava uma chave própria e o grupo nunca se formava.


def _decolar(numero: int, mes: int, description: str) -> TxFalsa:
    """As quatro parcelas Decolar como o banco de fato as gravou (compra de abr/2026 em 6x)."""
    return TxFalsa(
        date=datetime(2026, mes, 10, tzinfo=UTC),
        description=description,
        installment_number=numero,
        total_installments=6,
        total_amount_centavos=None,
    )


def test_contador_de_parcela_na_descricao_nao_separa_o_grupo() -> None:
    a = _decolar(1, 4, "Decolar Com 1/6")
    b = _decolar(2, 5, "Decolar Com 2/6")
    assert chave_compra(a) == chave_compra(b)


def test_sufixo_societario_nao_separa_o_grupo() -> None:
    """ "Decolar Com 1/6" e "DECOLAR COM LTDA 5/6" são a MESMA compra — o cartão trocou a forma."""
    a = _decolar(1, 4, "Decolar Com 1/6")
    b = _decolar(5, 8, "DECOLAR COM LTDA 5/6")
    assert chave_compra(a) == chave_compra(b)


def test_contador_de_dois_digitos_tambem_sai() -> None:
    a = TxFalsa(
        date=datetime(2025, 12, 25, tzinfo=UTC),
        description="Shoppingdefilhote 1/10",
        installment_number=1,
        total_installments=10,
        total_amount_centavos=None,
    )
    b = TxFalsa(
        date=datetime(2026, 9, 25, tzinfo=UTC),
        description="ShoppingDeFilhote 10/10",
        installment_number=10,
        total_installments=10,
        total_amount_centavos=None,
    )
    assert chave_compra(a) == chave_compra(b)


def test_barra_no_meio_do_nome_nao_e_contador() -> None:
    """Só o fim da string é contador — "24/7" no meio do nome é parte do estabelecimento."""
    a = TxFalsa(description="Loja 24/7 Centro")
    b = TxFalsa(description="Loja Centro")
    assert chave_compra(a) != chave_compra(b)


def test_estabelecimentos_diferentes_continuam_separados() -> None:
    """O risco de tirar pedaços da descrição é colar compras que não são a mesma."""
    a = _decolar(1, 4, "Decolar Com 1/6")
    b = _decolar(1, 4, "Hyundai Alphaville 1/6")
    assert chave_compra(a) != chave_compra(b)


# --- propagação via API ---------------------------------------------------------------------


@pytest.fixture
def categorias(db: Session) -> None:
    for cid in ("02000000", "03000000"):
        db.add(Categoria(pluggy_id=cid, description=cid))
    db.commit()


def _parcela(db: Session, usuario: Usuario, conta_id: int, numero: int, mes: int, **campos):
    tx = Transacao(
        usuario_id=usuario.id,
        conta_id=conta_id,
        pluggy_transaction_id=f"tx-{usuario.id}-{conta_id}-{campos.get('sufixo', '')}-{numero}",
        date=datetime(2026, mes, 10, tzinfo=UTC),
        amount_centavos=-10000,
        currency_code="BRL",
        type="DEBIT",
        status="POSTED",
        description="LOJA X",
        installment_number=numero,
        total_installments=3,
        total_amount_centavos=30000,
        categoria_pluggy_id="02000000",
        **{k: v for k, v in campos.items() if k != "sufixo"},
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx


def test_mudar_a_categoria_de_uma_parcela_muda_todas(
    client_factory, db: Session, usuario_a: Usuario, categorias
) -> None:
    conta = criar_conta(db, usuario_a.id, "acc-a")
    parcelas = [_parcela(db, usuario_a, conta.id, n, mes) for n, mes in ((1, 1), (2, 2), (3, 3))]

    resposta = client_factory(usuario_a).patch(
        f"/api/transacoes/{parcelas[1].id}",
        json={"categoria_override_id": "03000000", "categoria_ajustada_usuario": True},
    )
    assert resposta.status_code == 200, resposta.text

    for p in parcelas:
        db.refresh(p)
        assert p.categoria_override_id == "03000000"
        assert p.categoria_ajustada_usuario is True


def test_resposta_diz_quantas_parcelas_foram_junto(
    client_factory, db: Session, usuario_a: Usuario, categorias
) -> None:
    """A UI anuncia a propagação por este número. Anunciar por `total_installments > 1` prometia
    o que não tinha acontecido quando o agrupamento não achava irmã nenhuma."""
    conta = criar_conta(db, usuario_a.id, "acc-a")
    parcelas = [_parcela(db, usuario_a, conta.id, n, mes) for n, mes in ((1, 1), (2, 2), (3, 3))]

    corpo = client_factory(usuario_a).patch(
        f"/api/transacoes/{parcelas[0].id}", json={"categoria_override_id": "03000000"}
    )
    assert corpo.json()["parcelas_atualizadas"] == 2  # as OUTRAS duas


def test_sem_irma_a_resposta_nao_promete_propagacao(
    client_factory, db: Session, usuario_a: Usuario, categorias
) -> None:
    """Parcelada, mas sozinha no banco (as irmãs ainda não foram lançadas)."""
    conta = criar_conta(db, usuario_a.id, "acc-a")
    sozinha = _parcela(db, usuario_a, conta.id, 1, 1)

    corpo = client_factory(usuario_a).patch(
        f"/api/transacoes/{sozinha.id}", json={"categoria_override_id": "03000000"}
    )
    assert corpo.json()["parcelas_atualizadas"] == 0


def test_propagacao_nao_alcanca_outra_compra(
    client_factory, db: Session, usuario_a: Usuario, categorias
) -> None:
    conta = criar_conta(db, usuario_a.id, "acc-a")
    minha = _parcela(db, usuario_a, conta.id, 1, 1, sufixo="a")
    # Mesmo valor, mesmo estabelecimento, mesmo nº de parcelas — mas comprada em maio.
    outra = _parcela(db, usuario_a, conta.id, 1, 5, sufixo="b")

    client_factory(usuario_a).patch(
        f"/api/transacoes/{minha.id}", json={"categoria_override_id": "03000000"}
    )
    db.refresh(outra)
    assert outra.categoria_override_id is None


def test_propagacao_nao_atravessa_usuario(
    client_factory, db: Session, usuario_a: Usuario, usuario_b: Usuario, categorias
) -> None:
    conta_a = criar_conta(db, usuario_a.id, "acc-a")
    conta_b = criar_conta(db, usuario_b.id, "acc-b")
    de_a = _parcela(db, usuario_a, conta_a.id, 1, 1)
    de_b = _parcela(db, usuario_b, conta_b.id, 2, 2)

    client_factory(usuario_a).patch(
        f"/api/transacoes/{de_a.id}", json={"categoria_override_id": "03000000"}
    )
    db.refresh(de_b)
    assert de_b.categoria_override_id is None


def test_transacao_avulsa_nao_propaga_nada(
    client_factory, db: Session, usuario_a: Usuario, categorias
) -> None:
    conta = criar_conta(db, usuario_a.id, "acc-a")
    avulsa = Transacao(
        usuario_id=usuario_a.id,
        conta_id=conta.id,
        pluggy_transaction_id="tx-avulsa",
        date=datetime(2026, 1, 10, tzinfo=UTC),
        amount_centavos=-10000,
        currency_code="BRL",
        type="DEBIT",
        status="POSTED",
        description="LOJA X",
    )
    outra = Transacao(
        usuario_id=usuario_a.id,
        conta_id=conta.id,
        pluggy_transaction_id="tx-avulsa-2",
        date=datetime(2026, 1, 11, tzinfo=UTC),
        amount_centavos=-10000,
        currency_code="BRL",
        type="DEBIT",
        status="POSTED",
        description="LOJA X",
    )
    db.add_all([avulsa, outra])
    db.commit()

    client_factory(usuario_a).patch(
        f"/api/transacoes/{avulsa.id}", json={"categoria_override_id": "03000000"}
    )
    db.refresh(outra)
    assert outra.categoria_override_id is None


def test_parcela_vinculada_a_assinatura_nao_e_sobrescrita(
    client_factory, db: Session, usuario_a: Usuario, categorias
) -> None:
    """A categoria dela vem da assinatura — mudar o override ali seria escrever um campo inerte."""
    conta = criar_conta(db, usuario_a.id, "acc-a")
    assinatura = Assinatura(
        usuario_id=usuario_a.id,
        nome="Plano",
        valor_centavos=10000,
        periodicidade="mensal",
        categoria_id="02000000",
        nomes_transacao=[],
    )
    db.add(assinatura)
    db.commit()

    primeira = _parcela(db, usuario_a, conta.id, 1, 1)
    com_assinatura = _parcela(db, usuario_a, conta.id, 2, 2, assinatura_id=assinatura.id)

    client_factory(usuario_a).patch(
        f"/api/transacoes/{primeira.id}", json={"categoria_override_id": "03000000"}
    )
    db.refresh(com_assinatura)
    assert com_assinatura.categoria_override_id is None
