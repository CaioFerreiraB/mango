"""Aviso no Telegram quando o gasto de uma categoria cruza o % definido nas Preferências.

Só despesa (receita não "estoura", mesma regra de `alerta_atingido`), só linhas com `notificar`
e no máximo **um aviso por categoria por mês** (`orcamento_mensal.alerta_enviado_em`). Roda no
pós-processamento do sync (`app.services.sync`), que é quando o gasto muda.

ponytail: recategorizar à mão só avisa no próximo sync; chamar também no PATCH de transação se
precisar ser imediato.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.categoria import Categoria
from app.models.orcamento import OrcamentoMensal
from app.models.telegram import ConfigTelegram
from app.models.usuario import Usuario
from app.schemas.orcamento import OrcamentoConsumoItem
from app.services import telegram
from app.services.orcamento_consumo import consumo_do_mes
from app.services.periodo import hoje_sp
from app.telegram_client import TelegramClient, TelegramError

logger = logging.getLogger("app.orcamento_alerta")

_MESES = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)  # fmt: skip


def _brl(centavos: int) -> str:
    reais, cent = divmod(abs(centavos), 100)
    return "R$ " + f"{reais:,}".replace(",", ".") + f",{cent:02d}"


def verificar_e_avisar(db: Session, usuario_id: int) -> int:
    """Envia (numa mensagem só) as categorias que cruzaram o % neste mês e ainda não foram
    avisadas. Devolve quantas categorias entraram no aviso. Nunca propaga erro do Telegram."""
    with telegram.lock:
        geral = telegram.instancia(db)
        usuario = db.get(Usuario, usuario_id)
        config = db.scalar(select(ConfigTelegram).where(ConfigTelegram.usuario_id == usuario_id))
        if not telegram.pronto(geral, config, usuario):
            return 0

        hoje = hoje_sp()
        consumo = consumo_do_mes(db, usuario_id, hoje.year, hoje.month)
        cruzou = {
            i.orcamento_mensal_id: i
            for i in consumo.itens
            if i.tipo == "despesa"
            and not i.suprimido
            and i.notificar
            and i.percentual >= usuario.orcamento_alerta_pct
        }
        if not cruzou:
            return 0
        linhas = db.scalars(
            select(OrcamentoMensal).where(
                OrcamentoMensal.usuario_id == usuario_id,
                OrcamentoMensal.id.in_(cruzou),
                OrcamentoMensal.alerta_enviado_em.is_(None),
            )
        ).all()
        if not linhas:
            return 0

        # Marca ANTES do envio: crash depois daqui vira "não avisado", nunca reenvio em loop.
        momento = telegram.agora()
        for linha in linhas:
            linha.alerta_enviado_em = momento
        db.commit()

        nomes = {
            cid: traduzido or original
            for cid, traduzido, original in db.execute(
                select(
                    Categoria.pluggy_id, Categoria.description_translated, Categoria.description
                ).where(Categoria.pluggy_id.in_({ln.categoria_id for ln in linhas}))
            ).all()
        }
        texto = _mensagem(usuario.orcamento_alerta_pct, hoje.month, linhas, cruzou, nomes)
        try:
            with TelegramClient(geral.telegram_token_cifrado) as cliente:
                cliente.send_message(config.chat_id, texto)
        except TelegramError as exc:
            if exc.codigo != "envio_incerto":
                # Certamente não entregue: desmarca para o próximo sync tentar de novo.
                for linha in linhas:
                    linha.alerta_enviado_em = None
                db.commit()
            telegram.registrar_erro(db, geral, config, exc)
            logger.warning("alerta de orçamento usuario=%s codigo=%s", usuario_id, exc.codigo)
            return 0
        return len(linhas)


def _mensagem(
    pct: int,
    mes: int,
    linhas: list[OrcamentoMensal],
    cruzou: dict[int, OrcamentoConsumoItem],
    nomes: dict[str, str],
) -> str:
    partes = [
        "**Mango · orçamento**",
        f"Categorias que passaram de {pct}% em {_MESES[mes - 1]}:",
        "",
    ]
    for linha in linhas:
        item = cruzou[linha.id]
        nome = nomes.get(linha.categoria_id) or linha.categoria_id
        partes.append(
            f"{nome}: {item.percentual}% · {_brl(item.realizado_centavos)} de "
            f"{_brl(item.limite_centavos)}"
        )
    return "\n".join(partes)
