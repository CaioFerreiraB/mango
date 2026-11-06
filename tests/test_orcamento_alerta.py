"""Aviso de orçamento no Telegram: % das Preferências, switch por categoria, 1× por mês."""

from datetime import datetime, time

from app.models.categoria import Categoria
from app.models.usuario import Usuario
from app.repositories.orcamento import OrcamentoRepository
from app.repositories.transacao import TransacaoRepository
from app.services.orcamento_alerta import verificar_e_avisar
from app.services.orcamento_mensal import materializar_mes
from app.services.periodo import SP, hoje_sp
from tests.helpers import criar_conta
from tests.test_telegram import configurar, telegram_ok, vincular  # noqa: F401

MERCADO, BAR, SALARIO = "10010000", "10020000", "10030000"


def _cenario(db, usuario: Usuario) -> None:
    for cid, nome in ((MERCADO, "Supermercado"), (BAR, "Bares"), (SALARIO, "Salário")):
        db.add(Categoria(pluggy_id=cid, description=nome))
    db.commit()
    repo = OrcamentoRepository(db, usuario.id)
    repo.create(categoria_id=MERCADO, tipo="despesa", limite_padrao_centavos=10_000, ordem=0)
    repo.create(
        categoria_id=BAR, tipo="despesa", limite_padrao_centavos=1_000, ordem=1, notificar=False
    )
    repo.create(categoria_id=SALARIO, tipo="receita", limite_padrao_centavos=100, ordem=0)
    hoje = hoje_sp()
    materializar_mes(db, usuario.id, hoje.year, hoje.month)
    conta = criar_conta(db, usuario.id, f"acc-alerta-{usuario.id}")
    quando = datetime.combine(hoje, time(12), tzinfo=SP)
    for pid, valor, cat, tipo in (
        ("mercado", -8_500, MERCADO, "DEBIT"),  # 85% → avisa
        ("bar", -950, BAR, "DEBIT"),  # 95%, mas notificar=False
        ("salario", 20_000, SALARIO, "CREDIT"),  # receita nunca avisa
    ):
        TransacaoRepository(db, usuario.id).create(
            conta_id=conta.id,
            pluggy_transaction_id=f"{pid}-{usuario.id}",
            date=quando,
            amount_centavos=valor,
            currency_code="BRL",
            type=tipo,
            status="POSTED",
            categoria_pluggy_id=cat,
            eh_transferencia=False,
        )


def test_avisa_uma_vez_respeitando_switch_e_tipo(client_factory, db, usuario_a, request):
    enviados = request.getfixturevalue("telegram_ok")
    cliente = client_factory(usuario_a)
    configurar(cliente)
    vincular(cliente, db)
    _cenario(db, usuario_a)

    assert verificar_e_avisar(db, usuario_a.id) == 1
    ((args, _),) = enviados
    texto = args[1]
    assert "Supermercado: 85%" in texto and "R$ 85,00 de R$ 100,00" in texto
    assert "Bares" not in texto and "Salário" not in texto

    # Já avisado neste mês → não repete.
    assert verificar_e_avisar(db, usuario_a.id) == 0
    assert len(enviados) == 1


def test_respeita_percentual_das_preferencias(client_factory, db, usuario_a, request):
    enviados = request.getfixturevalue("telegram_ok")
    cliente = client_factory(usuario_a)
    configurar(cliente)
    vincular(cliente, db)
    _cenario(db, usuario_a)
    assert cliente.patch("/api/perfil", json={"orcamento_alerta_pct": 90}).status_code == 200
    assert cliente.patch("/api/perfil", json={"orcamento_alerta_pct": 0}).status_code == 422
    db.expire_all()
    assert verificar_e_avisar(db, usuario_a.id) == 0  # 85% < 90%
    assert enviados == []


def test_sem_telegram_vinculado_nao_envia(db, usuario_a, request):
    enviados = request.getfixturevalue("telegram_ok")
    _cenario(db, usuario_a)
    assert verificar_e_avisar(db, usuario_a.id) == 0
    assert enviados == []
