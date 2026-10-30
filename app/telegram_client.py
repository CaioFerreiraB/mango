"""Bot API via httpx. Falhas sanitizadas; envio ambíguo nunca é repetido aqui."""

import logging
import re

import httpx


class _RedigirToken(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # O Bot API põe o segredo na URL; inclusive logs de debug do transporte o contêm.
        mensagem = record.getMessage()
        redigida = re.sub(r"bot[0-9]+:[A-Za-z0-9_-]+", "bot[redigido]", mensagem)
        if redigida != mensagem:
            record.msg, record.args = redigida, ()
        return True


for _nome in ("httpx", "httpcore.http11", "httpcore.http2", "httpcore.connection"):
    logging.getLogger(_nome).addFilter(_RedigirToken())


class TelegramError(Exception):
    def __init__(self, codigo: str, *, repetir: bool = False, espera: int = 60):
        super().__init__(codigo)
        self.codigo, self.repetir, self.espera = codigo, repetir, espera


class TelegramClient:
    def __init__(self, token: str):
        self._http = httpx.Client(
            base_url=f"https://api.telegram.org/bot{token}/", timeout=10, follow_redirects=False
        )

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self._http.close()

    def _request(self, metodo: str, dados: dict | None = None, *, envio: bool = False):
        try:
            resposta = self._http.post(
                metodo, json=dados or {}, timeout=35 if metodo == "getUpdates" else 10
            )
        except (httpx.ConnectError, httpx.ConnectTimeout):
            raise TelegramError("sem_conexao", repetir=True) from None
        except httpx.HTTPError:
            raise TelegramError("envio_incerto" if envio else "sem_conexao") from None
        try:
            corpo = resposta.json()
            if not isinstance(corpo, dict):
                raise ValueError
        except ValueError:
            raise TelegramError("envio_incerto" if envio else "resposta_invalida") from None
        if resposta.is_success and corpo.get("ok") is True and "result" in corpo:
            return corpo["result"]
        status = corpo.get("error_code", resposta.status_code)
        if not isinstance(status, int) or isinstance(status, bool):
            raise TelegramError("envio_incerto" if envio else "resposta_invalida")
        if status == 401:
            raise TelegramError("token_invalido")
        if status == 403:
            raise TelegramError("destinatario_bloqueou")
        if status == 409:
            raise TelegramError("bot_em_uso")
        if status == 429:
            parametros = corpo.get("parameters")
            espera = parametros.get("retry_after", 60) if isinstance(parametros, dict) else 60
            if not isinstance(espera, int) or isinstance(espera, bool) or espera < 1:
                espera = 60
            raise TelegramError("limite_telegram", repetir=True, espera=espera)
        raise TelegramError("envio_incerto" if envio and status >= 500 else "requisicao_rejeitada")

    def get_me(self) -> dict:
        result = self._request("getMe")
        if (
            not isinstance(result, dict)
            or not isinstance(result.get("id"), int)
            or not result.get("username")
        ):
            raise TelegramError("resposta_invalida")
        return result

    def webhook_info(self) -> dict:
        result = self._request("getWebhookInfo")
        if not isinstance(result, dict) or "url" not in result:
            raise TelegramError("resposta_invalida")
        return result

    def updates(self, offset: int) -> list[dict]:
        result = self._request(
            "getUpdates",
            {"offset": offset, "timeout": 25, "allowed_updates": ["message", "callback_query"]},
        )
        if not isinstance(result, list):
            raise TelegramError("resposta_invalida")
        return result

    def send_message(
        self,
        chat_id: str,
        texto: str,
        url: str | None = None,
        *,
        web_app: bool = False,
        botoes: list | None = None,
    ) -> int:
        dados = {"chat_id": chat_id, "text": texto, "link_preview_options": {"is_disabled": True}}
        if url:
            dados["reply_markup"] = {
                "inline_keyboard": [
                    [
                        {
                            "text": "Revisar transações" if web_app else "Revisar no Mango",
                            **({"web_app": {"url": url}} if web_app else {"url": url}),
                        }
                    ]
                ]
            }
        if botoes:
            dados["reply_markup"] = {"inline_keyboard": botoes}
        result = self._request("sendMessage", dados, envio=True)
        if not isinstance(result, dict) or not isinstance(result.get("message_id"), int):
            raise TelegramError("envio_incerto")
        return result["message_id"]

    def menu(self, url: str | None) -> None:
        self._request(
            "setChatMenuButton",
            {
                "menu_button": {"type": "web_app", "text": "Abrir Mango", "web_app": {"url": url}}
                if url
                else {"type": "default"}
            },
        )

    def callback(self, callback_id: str) -> None:
        self._request("answerCallbackQuery", {"callback_query_id": callback_id})
