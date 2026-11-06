"""Bot API via httpx. Falhas sanitizadas; envio ambíguo nunca é repetido aqui."""

import html
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


_INLINE = [
    (re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*"), r"<b>\1</b>"),
    (re.compile(r"(?<!\w)__(?=\S)(.+?)(?<=\S)__(?!\w)"), r"<b>\1</b>"),
    (re.compile(r"~~(?=\S)(.+?)(?<=\S)~~"), r"<s>\1</s>"),
    (re.compile(r"\|\|(?=\S)(.+?)(?<=\S)\|\|"), r"<tg-spoiler>\1</tg-spoiler>"),
    # Sem colar em palavra: não pega `snake_case` nem "PAG*LOJA" de descrição de cartão.
    (re.compile(r"(?<![\w*])\*(?=[^\s*])(.+?)(?<=[^\s*])\*(?![\w*])"), r"<i>\1</i>"),
    (re.compile(r"(?<!\w)_(?=\S)(.+?)(?<=\S)_(?!\w)"), r"<i>\1</i>"),
    (re.compile(r"\[([^\]\n]+)\]\((https?://[^\s)\"]+)\)"), r'<a href="\2">\1</a>'),
]


_TABELA = re.compile(
    r"(?m)^[ \t]*\|.*\|[ \t]*\n[ \t]*\|[ \t:|-]*-[ \t:|-]*\|[ \t]*(?:\n[ \t]*\|.*\|[ \t]*)*"
)
_NUMERO = re.compile(r"[-+]?(R\$\s*)?[-+]?[\d.,]+\s*%?")


def _tabela(bloco: str) -> str:
    """Tabela Markdown → texto monoespaçado alinhado (o Telegram não tem tabela)."""
    linhas = [ln.strip().strip("|") for ln in bloco.split("\n")]
    del linhas[1]  # separador |---|
    celulas = [[re.sub(r"\*\*|__|`", "", c).strip() for c in ln.split("|")] for ln in linhas]
    n = max(map(len, celulas))
    celulas = [c + [""] * (n - len(c)) for c in celulas]
    largura = [max(len(c[i]) for c in celulas) for i in range(n)]
    numerica = [all(_NUMERO.fullmatch(c[i]) for c in celulas[1:] if c[i]) for i in range(n)]
    return "\n".join(
        "  ".join(
            c.rjust(largura[i]) if i and numerica[i] else c.ljust(largura[i])
            for i, c in enumerate(linha)
        ).rstrip()
        for linha in celulas
    )


def _html(texto: str) -> str:
    """Markdown simples (o que o LLM escreve) → HTML do Telegram.

    Escapa tudo antes: texto de banco/LLM é dado. Só pares casados viram tag, então um trecho
    fatiado nunca gera HTML desbalanceado. Tabela → `<pre>` alinhado; `> citação` (recolhível
    acima de 3 linhas); `||spoiler||`. ponytail: subconjunto (sem aninhamento de lista); se o
    LLM passar a usar mais, trocar por uma lib de Markdown→Telegram.
    """
    guardados: list[str] = []

    def guardar(trecho: str) -> str:
        guardados.append(trecho)
        return f"\x00{len(guardados) - 1}\x00"

    texto = texto.replace("\x00", "")  # \x00 marca os trechos guardados
    s = _TABELA.sub(
        lambda m: guardar(f"<pre>{html.escape(_tabela(m[0]), quote=False)}</pre>"), texto
    )
    s = html.escape(s, quote=False)
    s = re.sub(
        r"```[^\n]*\n?(.*?)```",
        lambda m: guardar(f"<pre>{m[1].strip(chr(10))}</pre>"),
        s,
        flags=re.S,
    )
    s = re.sub(r"`([^`\n]+)`", lambda m: guardar(f"<code>{m[1]}</code>"), s)
    linhas: list[str] = []
    citacao: list[str] = []

    def fechar_citacao():
        if citacao:
            tag = "blockquote expandable" if len(citacao) > 3 else "blockquote"
            linhas.append(f"<{tag}>" + "\n".join(citacao) + "</blockquote>")
            citacao.clear()

    for linha in s.split("\n"):
        if m := re.match(r"\s{0,3}&gt;\s?(.*)$", linha):
            citacao.append(m[1])
            continue
        fechar_citacao()
        if m := re.match(r"\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", linha):
            linha = f"**{m[1]}**" if not m[1].startswith("**") else m[1]
        elif m := re.match(r"(\s*)[-*+]\s+(.*)$", linha):
            linha = f"{m[1]}• {m[2]}"
        elif re.fullmatch(r"\s*([-*_])(\s*\1){2,}\s*", linha):
            linha = ""
        linhas.append(linha)
    fechar_citacao()
    s = "\n".join(linhas)
    for padrao, troca in _INLINE:
        s = padrao.sub(troca, s)
    return re.sub(r"\x00(\d+)\x00", lambda m: guardados[int(m[1])], s)


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
        dados = {
            "chat_id": chat_id,
            "text": _html(texto),
            "parse_mode": "HTML",
            "link_preview_options": {"is_disabled": True},
        }
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
        try:
            result = self._request("sendMessage", dados, envio=True)
        except TelegramError as exc:
            # 400 = certamente não entregue (sem risco de duplicar): HTML recusado não pode
            # custar a mensagem → reenvia uma vez como texto puro.
            if exc.codigo != "requisicao_rejeitada":
                raise
            dados["text"] = texto
            del dados["parse_mode"]
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
