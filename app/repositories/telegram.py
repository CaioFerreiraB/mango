"""Repositório de configuração do Telegram (§4.12) — 1 por usuário."""

from app.models.telegram import ConfigTelegram
from app.repositories.base import UserScopedRepository


class ConfigTelegramRepository(UserScopedRepository[ConfigTelegram]):
    model = ConfigTelegram
