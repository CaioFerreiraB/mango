"""Rotina diária com relógio/HTTP controlados, nos dois bancos."""

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.telegram import ExecucaoDiaria
from app.repositories.transacao import TransacaoRepository
from app.services import telegram
from app.telegram_client import TelegramError
from tests.helpers import criar_conta
from tests.test_telegram import configurar, telegram_ok, vincular  # noqa: F401
from tests.test_transacao import _criar_tx

MOMENTO = datetime(2026, 10, 29, 12, tzinfo=UTC)


@pytest.fixture
def rotina(db, usuario_a, client_factory, request, monkeypatch):
    from app.services import rotina_diaria as rotina

    enviados = request.getfixturevalue("telegram_ok")
    conta = criar_conta(db, usuario_a.id, "conta-diaria")
    cliente = client_factory(usuario_a)
    configurar(cliente)
    monkeypatch.setattr(telegram, "agora", lambda: MOMENTO)
    vincular(cliente, db)
    cliente.patch("/api/telegram", json={"notif_nao_revisadas": True})
    cliente.patch("/api/sync/configuracao", json={"sync_automatico": True})
    chamadas = []

    def sync(sessao, usuario_id):
        from app.models.pluggy import ItemPluggy

        for item in sessao.scalars(select(ItemPluggy).where(ItemPluggy.usuario_id == usuario_id)):
            item.ultimo_sync_em = MOMENTO
        sessao.commit()
        chamadas.append(usuario_id)

    monkeypatch.setattr(rotina, "sincronizar_usuario", sync)
    return rotina, conta, cliente, chamadas, enviados


def executar(rotina, session_factory, momento=MOMENTO):
    rotina.executar(session_factory=session_factory, momento=momento)


def test_relatorio_filtros_valores_isolamento_e_dedup(
    rotina, db, usuario_a, usuario_b, session_factory
):
    from app.models.categoria import CATEGORIA_PAGAMENTO_FATURA, Categoria

    mod, conta, cliente, chamadas, enviados = rotina
    repo = TransacaoRepository(db, usuario_a.id)
    usuario_a.revisao_desde = date(2026, 10, 1)
    db.add(Categoria(pluggy_id=CATEGORIA_PAGAMENTO_FATURA, description="Pagamento"))
    db.commit()
    for i in range(12):
        _criar_tx(
            repo,
            conta.id,
            f"diaria-{i}",
            date=MOMENTO,
            description=f"Loja {i}",
            amount_in_account_currency_centavos=-12345,
        )
    _criar_tx(repo, conta.id, "futura", date=MOMENTO + timedelta(days=1), description="FUTURA")
    _criar_tx(repo, conta.id, "antiga", date=MOMENTO - timedelta(days=50), description="ANTIGA")
    _criar_tx(
        repo,
        conta.id,
        "fatura",
        date=MOMENTO,
        description="FATURA",
        categoria_pluggy_id=CATEGORIA_PAGAMENTO_FATURA,
    )
    outra = criar_conta(db, usuario_b.id, "conta-b-diaria")
    _criar_tx(
        TransacaoRepository(db, usuario_b.id),
        outra.id,
        "segredo-b",
        date=MOMENTO,
        description="SEGREDO B",
    )
    executar(mod, session_factory)
    executar(mod, session_factory)
    assert len(enviados) == 1
    mensagem = enviados[0][0][1]
    assert "12 transações" in mensagem and "Mostrando 10 de 12" in mensagem
    assert "123,45" in mensagem and "Loja 11" in mensagem and "Loja 0\n" not in mensagem
    assert all(oculta not in mensagem for oculta in ("FUTURA", "ANTIGA", "FATURA", "SEGREDO B"))
    assert chamadas.count(usuario_a.id) == 1
    cliente.patch("/api/sync/configuracao", json={"sync_horario": "07:00"})
    executar(mod, session_factory)
    assert len(enviados) == 1


def test_fila_vazia_e_recuperacao_so_dia_atual(rotina, db, session_factory, usuario_a):
    mod, conta, _, chamadas, enviados = rotina
    executar(mod, session_factory, MOMENTO.replace(hour=10))  # 07:00 SP: ainda não
    assert chamadas == []
    executar(mod, session_factory)
    assert enviados == []
    registro = db.scalar(select(ExecucaoDiaria).where(ExecucaoDiaria.usuario_id == usuario_a.id))
    assert registro.data == MOMENTO.date() and registro.envio_status == "vazio"
    executar(mod, session_factory, MOMENTO + timedelta(days=3))
    assert len(chamadas) == 2
    assert len(db.scalars(select(ExecucaoDiaria)).all()) == 2


def test_erro_sync_nao_envia_e_retenta_sem_duplicar(
    rotina, session_factory, usuario_a, monkeypatch
):
    from app.pluggy.client import PluggyError

    mod, _, _, chamadas, enviados = rotina
    sync_ok = mod.sincronizar_usuario
    monkeypatch.setattr(
        mod, "sincronizar_usuario", lambda *a: (_ for _ in ()).throw(PluggyError("erro"))
    )
    executar(mod, session_factory)
    assert enviados == []
    monkeypatch.setattr(mod, "sincronizar_usuario", sync_ok)
    executar(mod, session_factory, MOMENTO + timedelta(minutes=4))
    assert chamadas == []
    executar(mod, session_factory, MOMENTO + timedelta(minutes=5))
    assert chamadas == [usuario_a.id]


@pytest.mark.parametrize(
    "codigo,repetir,esperado",
    [
        ("envio_incerto", False, "incerto"),
        ("limite_telegram", True, "pendente"),
        ("destinatario_bloqueou", False, "falhou"),
    ],
)
def test_erro_telegram_nao_repete_sync(
    rotina, db, usuario_a, session_factory, monkeypatch, codigo, repetir, esperado
):
    from app.telegram_client import TelegramClient

    mod, conta, _, chamadas, enviados = rotina
    _criar_tx(TransacaoRepository(db, usuario_a.id), conta.id, "erro-envio", date=MOMENTO)

    def falhar(*a, **kw):
        raise TelegramError(codigo, repetir=repetir, espera=120)

    monkeypatch.setattr(TelegramClient, "send_message", falhar)
    executar(mod, session_factory)
    db.expire_all()
    registro = db.scalar(select(ExecucaoDiaria))
    assert registro.envio_status == esperado
    monkeypatch.setattr(TelegramClient, "send_message", lambda *a, **kw: enviados.append(a) or 42)
    executar(mod, session_factory, MOMENTO + timedelta(seconds=119))
    assert enviados == []
    executar(mod, session_factory, MOMENTO + timedelta(minutes=2))
    assert len(enviados) == (1 if repetir else 0)
    assert chamadas == [usuario_a.id]


def test_reinicio_marca_entrega_em_andamento_como_incerta(rotina, db, usuario_a, session_factory):
    mod, _, _, chamadas, enviados = rotina
    db.add(
        ExecucaoDiaria(
            usuario_id=usuario_a.id,
            data=MOMENTO.date(),
            sync_status="concluido",
            envio_status="enviando",
        )
    )
    db.commit()
    mod.recuperar(session_factory=session_factory, momento=MOMENTO)
    executar(mod, session_factory)
    db.expire_all()
    assert db.scalar(select(ExecucaoDiaria)).envio_status == "incerto"
    assert chamadas == enviados == []


@pytest.mark.parametrize("cancelar", ["desvincular", "bot", "preferencia", "inativo"])
def test_cancelamento_antes_da_retentativa(
    rotina, db, usuario_a, session_factory, monkeypatch, cancelar
):
    from app.telegram_client import TelegramClient

    mod, conta, cliente, chamadas, enviados = rotina
    _criar_tx(TransacaoRepository(db, usuario_a.id), conta.id, "cancelar", date=MOMENTO)

    def limite(*a, **kw):
        raise TelegramError("limite_telegram", repetir=True, espera=60)

    monkeypatch.setattr(TelegramClient, "send_message", limite)
    executar(mod, session_factory)
    if cancelar == "desvincular":
        cliente.delete("/api/telegram/vinculo")
    elif cancelar == "bot":
        cliente.patch("/api/telegram/instancia", json={"ativo": False})
    elif cancelar == "preferencia":
        cliente.patch("/api/telegram", json={"notif_nao_revisadas": False})
    else:
        usuario_a.ativo = False
        db.commit()
    monkeypatch.setattr(TelegramClient, "send_message", lambda *a, **kw: enviados.append(a) or 42)
    executar(mod, session_factory, MOMENTO + timedelta(minutes=2))
    assert enviados == [] and chamadas == [usuario_a.id]


def test_sync_parcial_nao_autoriza_relatorio(rotina, db, usuario_a, session_factory, monkeypatch):
    from app.models.pluggy import ItemPluggy

    mod, conta, _, chamadas, enviados = rotina
    item = db.get(ItemPluggy, conta.item_id)
    db.add(
        ItemPluggy(
            usuario_id=usuario_a.id, credencial_id=item.credencial_id, pluggy_item_id="segundo-item"
        )
    )
    db.commit()
    _criar_tx(TransacaoRepository(db, usuario_a.id), conta.id, "parcial", date=MOMENTO)
    sync_ok = mod.sincronizar_usuario

    def parcial(sessao, usuario_id):
        sessao.get(ItemPluggy, conta.item_id).ultimo_sync_em = MOMENTO
        sessao.commit()

    monkeypatch.setattr(mod, "sincronizar_usuario", parcial)
    executar(mod, session_factory)
    assert enviados == []
    monkeypatch.setattr(mod, "sincronizar_usuario", sync_ok)
    executar(mod, session_factory, MOMENTO + timedelta(minutes=5))
    assert len(enviados) == 1 and chamadas == [usuario_a.id]


def test_falha_de_um_usuario_nao_interrompe_outro(
    rotina, db, usuario_a, usuario_b, client_factory, session_factory, monkeypatch
):
    from app.config import settings
    from app.pluggy.client import PluggyError

    mod, _, _, chamadas, enviados = rotina
    conta_b = criar_conta(db, usuario_b.id, "conta-b-continua")
    cliente_b = client_factory(usuario_b)
    vincular(cliente_b, db, telegram_id=789)
    cliente_b.patch("/api/telegram", json={"notif_nao_revisadas": True})
    _criar_tx(
        TransacaoRepository(db, usuario_b.id),
        conta_b.id,
        "continua",
        date=MOMENTO,
        description="Só B",
    )
    sync_ok = mod.sincronizar_usuario

    def sincronizar(sessao, usuario_id):
        if usuario_id == usuario_a.id:
            raise PluggyError("falha do provedor")
        sync_ok(sessao, usuario_id)

    monkeypatch.setattr(mod, "sincronizar_usuario", sincronizar)
    monkeypatch.setattr(settings, "app_mode", "self_hosted")
    executar(mod, session_factory)
    assert chamadas == [usuario_b.id]
    assert len(enviados) == 1 and enviados[0][0][0] == "789"
    assert "Só B" in enviados[0][0][1]


def test_agendador_preserva_jobs_por_modo(monkeypatch):
    from app.config import settings
    from app.services import agendador

    class Scheduler:
        def __init__(self, **kw):
            self.jobs = {}

        def add_job(self, func, **kw):
            self.jobs[kw["id"]] = kw

        def start(self):
            pass

        def shutdown(self, **kw):
            pass

    monkeypatch.setattr(agendador, "BackgroundScheduler", Scheduler)
    monkeypatch.setattr(agendador, "_scheduler", None)
    for modo, quantidade in (("local", 1), ("self_hosted", 4)):
        monkeypatch.setattr(settings, "app_mode", modo)
        agendador.iniciar()
        assert len(agendador._scheduler.jobs) == quantidade
        job = agendador._scheduler.jobs["rotina_diaria"]
        assert job["max_instances"] == 1 and job["coalesce"] is True
        agendador.parar()
