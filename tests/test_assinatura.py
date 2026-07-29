"""Assinaturas (§4.7): CRUD, resumo agregado, heurística de detecção e idempotência."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.categoria import Categoria
from app.models.usuario import Usuario
from app.repositories.assinatura import AssinaturaRepository
from app.repositories.transacao import TransacaoRepository
from app.services.assinatura import resumo
from app.services.assinatura_deteccao import (
    TxAssinatura,
    candidatos,
    candidatos_novos,
)
from tests.helpers import criar_conta


def test_crud_completo(client_factory, usuario_a: Usuario) -> None:
    client = client_factory(usuario_a)
    criado = client.post(
        "/api/assinaturas",
        json={"nome": "Netflix", "valor_centavos": 2990, "periodicidade": "mensal"},
    )
    assert criado.status_code == 201, criado.text
    aid = criado.json()["id"]

    assert client.patch(f"/api/assinaturas/{aid}", json={"ativa": False}).json()["ativa"] is False
    assert client.delete(f"/api/assinaturas/{aid}").status_code == 204
    assert client.get(f"/api/assinaturas/{aid}").status_code == 404


def test_resumo_normaliza_para_mensal_e_exclui_inativa(db: Session, usuario_a: Usuario) -> None:
    db.add_all(
        [
            Categoria(pluggy_id="07010000", description="a"),
            Categoria(pluggy_id="05000000", description="b"),
        ]
    )
    db.commit()
    repo = AssinaturaRepository(db, usuario_a.id)

    def _nova(nome: str, valor: int, per: str, cat: str | None = None, ativa: bool = True) -> None:
        repo.create(
            nome=nome, valor_centavos=valor, periodicidade=per, categoria_id=cat, ativa=ativa
        )

    _nova("Netflix", 2990, "mensal", "07010000")
    _nova("Amazon", 12_000, "anual", "07010000")  # anual/12 = 1000/mês
    _nova("Spotify", 1990, "mensal", "05000000")
    _nova("Antigo", 9999, "mensal", ativa=False)  # inativa → fora

    r = resumo(db, usuario_a.id)
    assert r.total_mensal_centavos == 2990 + 1000 + 1990  # anual/12 = 1000
    por = {c.categoria_id: c.total_mensal_centavos for c in r.por_categoria}
    assert por == {"07010000": 3990, "05000000": 1990}
    assert len(r.vigentes) == 3  # a inativa fica de fora


# --- heurística de detecção (função pura) --------------------------------------------


def _tx(mes: int, valor: int, **over) -> TxAssinatura:
    base = {
        "type": "DEBIT",
        "amount_in_account_currency_centavos": None,
        "currency_code": "BRL",
        "eh_transferencia": False,
        "total_installments": None,
        "merchant_cnpj": None,
        "merchant_nome": "Netflix",
        "description": None,
        "categoria_id": "07010000",
        "conta_id": 1,
    }
    base.update(over)
    return TxAssinatura(date=datetime(2026, mes, 10, tzinfo=UTC), amount_centavos=valor, **base)


def test_detecta_recorrencia_mensal() -> None:
    (cand,) = candidatos([_tx(m, -2990) for m in (3, 4, 5, 6)])
    assert cand.periodicidade == "mensal"
    assert cand.valor_centavos == 2990
    assert cand.nome == "Netflix"
    assert cand.ocorrencias == 4


def test_ignora_parcelas_transferencia_e_irregular() -> None:
    parcelas = [_tx(m, -10_000, total_installments=12, merchant_nome="Loja") for m in (3, 4, 5)]
    transferencias = [_tx(m, -5000, eh_transferencia=True, merchant_nome="TED") for m in (3, 4, 5)]
    # Gaps 19d e 101d → mediana 60d, fora de qualquer bucket de periodicidade.
    irregular = [
        TxAssinatura(
            date=datetime(2026, mes, dia, tzinfo=UTC),
            amount_centavos=-1000,
            amount_in_account_currency_centavos=None,
            currency_code="BRL",
            type="DEBIT",
            eh_transferencia=False,
            total_installments=None,
            merchant_cnpj=None,
            merchant_nome="Aleatorio",
            description=None,
            categoria_id=None,
            conta_id=1,
        )
        for mes, dia in ((1, 1), (1, 20), (5, 1))
    ]
    assert candidatos(parcelas + transferencias + irregular) == []


def test_valores_dispersos_nao_viram_assinatura() -> None:
    # Mesmo estabelecimento e cadência mensal, mas valores muito diferentes (compras avulsas).
    txs = [_tx(3, -1000), _tx(4, -9000), _tx(5, -3000)]
    assert candidatos(txs) == []


def test_candidato_brl_sem_moeda_estrangeira() -> None:
    (cand,) = candidatos([_tx(m, -2990) for m in (3, 4, 5, 6)])
    assert cand.moeda == "BRL"
    assert cand.valor_moeda_centavos is None
    assert cand.valor_centavos == 2990


def test_candidato_expoe_reais_e_moeda_estrangeira() -> None:
    # Compra internacional: valor nativo (USD) estável; o convertido em reais varia com o câmbio.
    reais = (-5500, -5600, -5550, -5500)
    txs = [
        _tx(
            m,
            -999,
            currency_code="USD",
            amount_in_account_currency_centavos=r,
            merchant_nome="OpenAI",
        )
        for m, r in zip((3, 4, 5, 6), reais, strict=True)
    ]
    (cand,) = candidatos(txs)
    assert cand.moeda == "USD"
    assert cand.valor_moeda_centavos == 999  # mediana na moeda estrangeira
    assert cand.valor_centavos == 5525  # mediana em reais (valor efetivo na conta)


def test_candidatos_novos_exclui_existentes(
    db: Session, usuario_a: Usuario, client_factory
) -> None:
    db.add(Categoria(pluggy_id="07010000", description="c"))
    db.commit()
    conta = criar_conta(db, usuario_a.id, "acc-det")
    repo = TransacaoRepository(db, usuario_a.id)
    for i, mes in enumerate((3, 4, 5, 6)):
        repo.create(
            conta_id=conta.id,
            pluggy_transaction_id=f"n{i}",
            date=datetime(2026, mes, 10, tzinfo=UTC),
            amount_centavos=-2990,
            currency_code="BRL",
            type="DEBIT",
            status="POSTED",
            merchant_nome="Netflix",
            categoria_pluggy_id="07010000",
        )

    (candidato,) = candidatos_novos(db, usuario_a.id)
    assert candidato.nome == "Netflix"
    assert candidato.periodicidade == "mensal"
    assert candidato.valor_centavos == 2990
    assert candidato.categoria_id == "07010000"

    # Endpoint HTTP: `/candidatos` não colide com `/{item_id}` e serializa o dataclass.
    client = client_factory(usuario_a)
    resp = client.get("/api/assinaturas/candidatos")
    assert resp.status_code == 200, resp.text
    (payload,) = resp.json()
    assert payload["nome"] == "Netflix"
    assert payload["ocorrencias"] == 4

    # Depois de virar assinatura (mesmo nome normalizado), some da busca.
    AssinaturaRepository(db, usuario_a.id).create(
        nome="netflix", valor_centavos=2990, periodicidade="mensal"
    )
    assert candidatos_novos(db, usuario_a.id) == []
    assert client.get("/api/assinaturas/candidatos").json() == []


def test_alias_exclui_candidato_renomeado(db: Session, usuario_a: Usuario) -> None:
    # Rótulo amigável ("Netflix") ≠ nome da transação: sem o alias, a busca re-sugeriria.
    db.add(Categoria(pluggy_id="07010000", description="c"))
    db.commit()
    conta = criar_conta(db, usuario_a.id, "acc-alias")
    repo = TransacaoRepository(db, usuario_a.id)
    for i, mes in enumerate((3, 4, 5, 6)):
        repo.create(
            conta_id=conta.id,
            pluggy_transaction_id=f"a{i}",
            date=datetime(2026, mes, 10, tzinfo=UTC),
            amount_centavos=-2990,
            currency_code="BRL",
            type="DEBIT",
            status="POSTED",
            merchant_nome="NETFLIX*BR 4155",
            categoria_pluggy_id="07010000",
        )
    AssinaturaRepository(db, usuario_a.id).create(
        nome="Netflix",
        valor_centavos=2990,
        periodicidade="mensal",
        nomes_transacao=["netflix*br 4155"],  # alias casa o nome da transação → some da busca
    )
    assert candidatos_novos(db, usuario_a.id) == []


def test_candidato_expoe_transacao_ids() -> None:
    txs = [_tx(m, -2990, id=m) for m in (3, 4, 5, 6)]
    (cand,) = candidatos(txs)
    assert set(cand.transacao_ids) == {3, 4, 5, 6}


def test_deteccao_ignora_nao_e_assinatura(db: Session, usuario_a: Usuario) -> None:
    # Transações marcadas "não é assinatura" saem da detecção → o candidato some da busca (§4.7).
    db.add(Categoria(pluggy_id="07010000", description="c"))
    db.commit()
    conta = criar_conta(db, usuario_a.id, "acc-nao")
    repo = TransacaoRepository(db, usuario_a.id)
    for i, mes in enumerate((3, 4, 5, 6)):
        repo.create(
            conta_id=conta.id,
            pluggy_transaction_id=f"x{i}",
            date=datetime(2026, mes, 10, tzinfo=UTC),
            amount_centavos=-2990,
            currency_code="BRL",
            type="DEBIT",
            status="POSTED",
            merchant_nome="Netflix",
            categoria_pluggy_id="07010000",
        )
    # Antes: é candidato e expõe os ids das transações do grupo.
    (cand,) = candidatos_novos(db, usuario_a.id)
    assert len(cand.transacao_ids) == 4
    # Marcar todas como "não é assinatura" → some da busca.
    for tid in cand.transacao_ids:
        repo.update(repo.get(tid), nao_e_assinatura=True)
    assert candidatos_novos(db, usuario_a.id) == []


def test_crud_nomes_transacao(client_factory, usuario_a: Usuario) -> None:
    client = client_factory(usuario_a)
    criado = client.post(
        "/api/assinaturas",
        json={
            "nome": "Spotify",
            "valor_centavos": 1990,
            "periodicidade": "mensal",
            "nomes_transacao": ["SPOTIFY BR"],
        },
    )
    assert criado.status_code == 201, criado.text
    assert criado.json()["nomes_transacao"] == ["SPOTIFY BR"]
    aid = criado.json()["id"]

    upd = client.patch(
        f"/api/assinaturas/{aid}", json={"nomes_transacao": ["SPOTIFY BR", "SPOTIFY*BR"]}
    )
    assert upd.json()["nomes_transacao"] == ["SPOTIFY BR", "SPOTIFY*BR"]


def test_editar_aliases_revincula_transacoes(
    client_factory, db: Session, usuario_a: Usuario
) -> None:
    # Editar `nomes_transacao` percorre as transações e (re)vincula as que casam pelo nome (§4.7):
    # a sem vínculo passa a apontar p/ a assinatura; a vinculada à assinatura errada é corrigida.
    conta = criar_conta(db, usuario_a.id, "acc-revinc")
    repo = TransacaoRepository(db, usuario_a.id)
    client = client_factory(usuario_a)
    outra = client.post(
        "/api/assinaturas",
        json={"nome": "Outra", "valor_centavos": 100, "periodicidade": "mensal"},
    ).json()["id"]

    def _tx_spotify(sufixo: str, mes: int, **extra):
        return repo.create(
            conta_id=conta.id,
            pluggy_transaction_id=sufixo,
            date=datetime(2026, mes, 10, tzinfo=UTC),
            amount_centavos=-1990,
            currency_code="BRL",
            type="DEBIT",
            status="POSTED",
            merchant_nome="SPOTIFY BR",
            **extra,
        )

    sem_vinculo = _tx_spotify("s0", 4)
    vinculo_errado = _tx_spotify("s1", 5, assinatura_id=outra)
    spotify = client.post(
        "/api/assinaturas",
        json={"nome": "Spotify", "valor_centavos": 1990, "periodicidade": "mensal"},
    ).json()["id"]

    upd = client.patch(f"/api/assinaturas/{spotify}", json={"nomes_transacao": ["spotify br"]})
    assert upd.status_code == 200, upd.text
    db.expire_all()
    assert repo.get(sem_vinculo.id).assinatura_id == spotify
    assert repo.get(vinculo_errado.id).assinatura_id == spotify
