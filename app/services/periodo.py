"""Cortes de período no fuso America/Sao_Paulo (§4.10).

Os limites saem em UTC (aware) para comparar com `transacao.date` de forma consistente nos
dois bancos. Centraliza a regra de "fim do dia" para dashboards e filtros.
"""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

SP = ZoneInfo("America/Sao_Paulo")


def limites_sp(inicio: date, fim: date) -> tuple[datetime, datetime]:
    """Intervalo [inicio 00:00, (fim+1) 00:00) no fuso SP, devolvido em UTC."""
    ini = datetime.combine(inicio, time.min, tzinfo=SP).astimezone(UTC)
    fim_excl = datetime.combine(fim + timedelta(days=1), time.min, tzinfo=SP).astimezone(UTC)
    return ini, fim_excl


def hoje_sp() -> date:
    """Dia civil de hoje no fuso SP."""
    return datetime.now(SP).date()


def janela_listagem(
    inicio: date | None, fim: date | None, *, ocultar_futuras: bool = False
) -> tuple[datetime | None, datetime | None]:
    """Limites [ini, fim) da listagem de transações, cada um resolvido no fuso SP e independente
    do outro. `None` em qualquer ponta = sem limite daquele lado.

    `ocultar_futuras` só APERTA o fim até o fim do dia de hoje. É corte de data, não predicado novo:
    dizer "sem lançamentos futuros" é dizer `fim <= hoje` (§4.2), e a listagem já sabe filtrar por
    fim. Uma segunda cláusula com o mesmo significado seria uma segunda voz sobre a mesma regra.
    """
    ini = limites_sp(inicio, inicio)[0] if inicio else None
    fim_dt = limites_sp(fim, fim)[1] if fim else None
    if ocultar_futuras:
        hoje = hoje_sp()
        corte = limites_sp(hoje, hoje)[1]
        fim_dt = corte if fim_dt is None else min(fim_dt, corte)
    return ini, fim_dt


def mes_corrente() -> tuple[date, date]:
    """(1º dia do mês, hoje) no fuso SP — período padrão do dashboard."""
    hoje = hoje_sp()
    return hoje.replace(day=1), hoje
