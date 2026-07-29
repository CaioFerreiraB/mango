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


def mes_corrente() -> tuple[date, date]:
    """(1º dia do mês, hoje) no fuso SP — período padrão do dashboard."""
    hoje = hoje_sp()
    return hoje.replace(day=1), hoje
