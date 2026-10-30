"""Contrato de credenciais temporárias e autenticação do Mini App."""

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest
from fastapi import HTTPException

from app.services.integracao_auth import validar_init_data


def assinatura(token, **campos):
    dados = {"auth_date": str(int(time.time())), "user": json.dumps({"id": 123}), **campos}
    segredo = hmac.digest(b"WebAppData", token.encode(), "sha256")
    dados["hash"] = hmac.new(
        segredo, "\n".join(f"{k}={v}" for k, v in sorted(dados.items())).encode(), hashlib.sha256
    ).hexdigest()
    return urlencode(dados)


def test_init_data_autentica_e_recusa_falsificacao():
    token = "123:segredo"
    assert validar_init_data(assinatura(token), token) == "123"
    for dados in [
        assinatura(token) + "&auth_date=0",
        assinatura(token, auth_date="1"),
        assinatura("outro"),
        "user={}",
    ]:
        with pytest.raises(HTTPException):
            validar_init_data(dados, token)
