"""Dois protocolos HTTP, sem SDK de agentes. Não repetir execuções de resultado incerto."""

import ipaddress
import json
import socket
from urllib.parse import urlsplit

import httpx

from app.config import settings
from app.exceptions import UpstreamError, ValidationError
from app.models.integracao import ConfigIntegracao


def validar_endpoint(valor: str) -> str:
    try:
        url = urlsplit(valor)
        _ = url.port
    except ValueError:
        raise ValidationError("endereço da API inválido") from None
    if (
        url.scheme != "https"
        or not url.hostname
        or url.username
        or url.password
        or url.query
        or url.fragment
        or any(c.isspace() for c in valor)
    ):
        raise ValidationError("informe um endpoint HTTPS, sem credenciais, consulta ou fragmento")
    try:
        porta = url.port or 443
        enderecos = socket.getaddrinfo(url.hostname, porta, type=socket.SOCK_STREAM)
    except (ValueError, OSError):
        raise ValidationError("não foi possível resolver o endereço da API") from None
    liberados = settings.ia_hosts_privados.split(",")
    if url.hostname not in liberados and any(
        not ipaddress.ip_address(item[4][0]).is_global for item in enderecos
    ):
        raise ValidationError("destino privado exige liberação do operador em IA_HOSTS_PRIVADOS")
    return valor.rstrip("/")


async def requisitar(
    config: ConfigIntegracao, metodo: str, caminho: str, *, corpo=None, headers=None
):
    endpoint = validar_endpoint(config.endpoint or "")
    try:
        async with httpx.AsyncClient(
            timeout=120, follow_redirects=False, trust_env=False
        ) as client:
            resposta = await client.request(
                metodo,
                endpoint + caminho,
                json=corpo,
                headers={"Authorization": f"Bearer {config.chave}", **(headers or {})},
            )
    except httpx.HTTPError:
        raise UpstreamError("provedor indisponível; execução não repetida") from None
    if resposta.status_code >= 300:
        falha(config, resposta)
    try:
        dados = resposta.json()
        if not isinstance(dados, dict):
            raise ValueError
        return dados
    except ValueError:
        raise UpstreamError("resposta inválida do provedor") from None


def falha(config: ConfigIntegracao, resposta: httpx.Response):
    """Traduz status HTTP do provedor em erro legível; nunca devolve."""
    if config.provedor == "axon":
        try:
            detalhe = resposta.json()
            erros = detalhe.get("x_axon", {}).get("errors", [])
            if any(
                e.get("kind") in {"McpUnavailable", "UnknownServer"}
                for e in erros
                if isinstance(e, dict)
            ):
                raise UpstreamError(
                    "MCP Mango inacessível ou autorização recusada; confira a configuração no Axon"
                )
        except (ValueError, AttributeError, TypeError):
            pass
    motivos = {
        401: "chave inválida",
        404: "Assistant ou endpoint indisponível",
        424: "Assistant indisponível",
        429: "limite do provedor atingido",
    }
    raise UpstreamError(
        motivos.get(resposta.status_code, "falha do provedor; execução não repetida")
    )


LINHA_MAX = 1 << 20  # 1 MiB: uma linha SSE sem fim não pode crescer a memória sem limite


def _evento_sse(dado: str):
    """Delta de texto de um `data:` (ou None); erro do provedor no meio do stream vira exceção."""
    try:
        evento = json.loads(dado)
        if not isinstance(evento, dict):
            raise ValueError
    except ValueError:
        raise UpstreamError("resposta inválida do provedor") from None
    extra = evento.get("x_axon")
    if evento.get("error") or (isinstance(extra, dict) and extra.get("errors")):
        raise UpstreamError("falha do provedor durante a resposta")
    try:
        delta = evento["choices"][0]["delta"].get("content")
    except (KeyError, IndexError, TypeError, AttributeError):
        return None
    return delta if isinstance(delta, str) and delta else None


async def transmitir(config: ConfigIntegracao, caminho: str, *, corpo, headers=None):
    """SSE no formato OpenAI: rende cada `choices[0].delta.content` até `[DONE]`.

    Sem `[DONE]` a resposta está incompleta (conexão cortada): erro, nunca texto parcial salvo.
    """
    endpoint = validar_endpoint(config.endpoint or "")
    try:
        async with (
            httpx.AsyncClient(timeout=120, follow_redirects=False, trust_env=False) as client,
            client.stream(
                "POST",
                endpoint + caminho,
                json=corpo,
                headers={"Authorization": f"Bearer {config.chave}", **(headers or {})},
            ) as resposta,
        ):
            if resposta.status_code >= 300:
                await resposta.aread()
                falha(config, resposta)
            resto = b""
            async for bloco in resposta.aiter_bytes():
                resto += bloco
                *linhas, resto = resto.split(b"\n")
                # Linha incompleta acumulada OU completa no mesmo bloco: ambas limitadas.
                if len(resto) > LINHA_MAX or any(len(x) > LINHA_MAX for x in linhas):
                    raise UpstreamError("resposta inválida do provedor")
                for crua in linhas:
                    linha = crua.decode("utf-8", "replace").rstrip("\r")
                    if not linha.startswith("data:"):
                        continue
                    dado = linha[5:].strip()
                    if dado == "[DONE]":
                        return
                    if delta := _evento_sse(dado):
                        yield delta
    except httpx.HTTPError:
        raise UpstreamError("provedor indisponível; execução não repetida") from None
    raise UpstreamError("resposta do provedor interrompida; tente novamente")


def descobrir_axon(dados: dict, mcp_url: str) -> str:
    candidatos = []
    if not isinstance(dados.get("data"), list):
        raise ValidationError("descoberta Axon inválida: lista de Assistants ausente")
    for item in dados["data"]:
        if not isinstance(item, dict):
            continue
        extra = item.get("x_axon")
        delegacao = extra.get("mcp_delegation") if isinstance(extra, dict) else None
        if not isinstance(delegacao, dict):
            continue
        if (
            type(delegacao.get("version")) is not int
            or delegacao.get("version") != 1
            or not delegacao.get("alias")
            or delegacao.get("endpoint") != mcp_url
        ):
            raise ValidationError("Assistant com delegação incompatível ou associado a outro MCP")
        if isinstance(item.get("id"), str) and item["id"]:
            candidatos.append(item["id"])
    if len(candidatos) != 1:
        raise ValidationError(
            "a chave deve acessar exatamente um Assistant com delegação MCP compatível"
        )
    return candidatos[0]


async def testar(config: ConfigIntegracao) -> str:
    if not config.chave:
        raise ValidationError("informe a chave de API")
    if config.provedor == "axon":
        if settings.app_mode != "self_hosted" or not config.url:
            raise ValidationError("Axon exige self-hosted e endereço HTTPS do Mango")
        return descobrir_axon(await requisitar(config, "GET", "/models"), config.url + "/mcp")
    dados = await requisitar(
        config,
        "POST",
        "/chat/completions",
        corpo={
            "model": config.modelo,
            "messages": [{"role": "user", "content": "Chame a ferramenta teste."}],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "teste",
                        "description": "Teste sem dados reais",
                        "parameters": {"type": "object", "properties": {}},
                    },
                }
            ],
            "tool_choice": {"type": "function", "function": {"name": "teste"}},
        },
    )
    try:
        if dados["choices"][0]["message"]["tool_calls"][0]["function"]["name"] != "teste":
            raise ValueError
    except (KeyError, IndexError, TypeError, ValueError):
        raise ValidationError(
            "o modelo precisa suportar tool calling compatível com OpenAI"
        ) from None
    return config.modelo
