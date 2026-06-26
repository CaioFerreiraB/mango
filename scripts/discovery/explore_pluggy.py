# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.27", "python-dotenv>=1.0"]
# ///
"""
Exploração da API do Pluggy — fase de descoberta do mango.

Script DESCARTÁVEL e idempotente: autentica no Pluggy, cria (ou reaproveita) um
item de sandbox e captura os JSONs crus dos endpoints que vamos modelar na Fase 0
(contas, transações, investimentos, faturas, categorias). Também sonda se a API
permite CRIAR categorias novas (decisão de produto: adotamos a taxonomia do Pluggy).

Uso:
    cp scripts/discovery/.env.example scripts/discovery/.env   # e preencha as credenciais
    uv run scripts/discovery/explore_pluggy.py

Saída: JSONs crus em scripts/discovery/raw/ (gitignorado) + resumo no stdout.
Nada aqui vira código de aplicação — é insumo para docs/dev/descoberta-pluggy.md.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

BASE_URL = "https://api.pluggy.ai"
SCRIPT_DIR = Path(__file__).resolve().parent
RAW_DIR = SCRIPT_DIR / "raw"

# Sandbox do Pluggy (docs/dev/descoberta): credenciais universais de teste.
SANDBOX_USER = "user-ok"
SANDBOX_PASSWORD = "password-ok"
SANDBOX_MFA_TOKEN = "123456"

# Estados terminais do item ao sincronizar.
ITEM_DONE = {"UPDATED", "OUTDATED", "LOGIN_ERROR", "ERROR"}
ITEM_WAITING = {"WAITING_USER_INPUT", "WAITING_USER_ACTION"}


def fail(msg: str) -> None:
    print(f"\n❌ {msg}", file=sys.stderr)
    sys.exit(1)


def save(name: str, data: Any) -> Path:
    """Grava JSON cru em raw/ e devolve o caminho."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / f"{name}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def request(
    client: httpx.Client,
    method: str,
    path: str,
    *,
    json_body: dict | None = None,
    params: dict | None = None,
    allow_error: bool = False,
) -> httpx.Response:
    """Chamada com tratamento de rate limit (429 → Retry-After)."""
    url = BASE_URL + path
    for _ in range(4):
        resp = client.request(method, url, json=json_body, params=params)
        if resp.status_code == 429:
            wait = int(resp.headers.get("Retry-After", "60"))
            print(f"   …rate limited, aguardando {wait}s")
            time.sleep(wait)
            continue
        break
    if not allow_error and resp.status_code >= 400:
        fail(f"{method} {path} → {resp.status_code}: {resp.text[:600]}")
    return resp


def authenticate(client: httpx.Client, client_id: str, client_secret: str) -> str:
    print("→ POST /auth (clientId/clientSecret → apiKey)")
    resp = request(
        client, "POST", "/auth",
        json_body={"clientId": client_id, "clientSecret": client_secret},
    )
    api_key = resp.json().get("apiKey")
    if not api_key:
        fail(f"/auth não retornou apiKey: {resp.text[:300]}")
    print("   ✓ apiKey obtida (validade ~2h)")
    return api_key


def pick_sandbox_connector(client: httpx.Client) -> int:
    print("→ GET /connectors?sandbox=true (descobrir connector de teste)")
    resp = request(client, "GET", "/connectors", params={"sandbox": "true"})
    connectors = resp.json().get("results", [])
    save("connectors_sandbox", connectors)
    if not connectors:
        fail("Nenhum connector de sandbox retornado.")
    # Preferimos um connector de credenciais simples (user/password).
    for c in connectors:
        names = {f.get("name") for f in (c.get("credentials") or [])}
        if {"user", "password"} <= names:
            print(f"   ✓ connector {c['id']} — {c.get('name')}")
            return int(c["id"])
    c = connectors[0]
    print(f"   ✓ connector {c['id']} — {c.get('name')} (fallback)")
    return int(c["id"])


def create_item(client: httpx.Client, connector_id: int) -> str:
    print(f"→ POST /items (connector {connector_id}, sandbox user)")
    resp = request(
        client, "POST", "/items",
        json_body={
            "connectorId": connector_id,
            "parameters": {"user": SANDBOX_USER, "password": SANDBOX_PASSWORD},
        },
    )
    item = resp.json()
    print(f"   ✓ item {item['id']} criado (status {item.get('status')})")
    return item["id"]


def wait_for_item(client: httpx.Client, item_id: str, timeout_s: int = 180) -> dict:
    print(f"→ aguardando sincronização do item {item_id}")
    deadline = time.time() + timeout_s
    sent_mfa = False
    while time.time() < deadline:
        item = request(client, "GET", f"/items/{item_id}").json()
        status = item.get("status")
        print(f"   …status: {status}")
        if status in ITEM_WAITING and not sent_mfa:
            print(f"   → enviando MFA de sandbox ({SANDBOX_MFA_TOKEN})")
            request(
                client, "PATCH", f"/items/{item_id}",
                json_body={"parameters": {"token": SANDBOX_MFA_TOKEN}},
                allow_error=True,
            )
            sent_mfa = True
        elif status in ITEM_DONE:
            save("item", item)
            if status != "UPDATED":
                print(f"   ⚠ item terminou em {status} (captura pode vir incompleta)")
            return item
        time.sleep(3)
    fail(f"Timeout esperando o item {item_id} sincronizar.")


def paginate(client: httpx.Client, path: str, params: dict, cap_pages: int = 5) -> list[dict]:
    """Coleta páginas (page/totalPages) até cap_pages. Usado por /investments, /bills."""
    results: list[dict] = []
    page = 1
    while page <= cap_pages:
        p = {**params, "pageSize": 500, "page": page}
        body = request(client, "GET", path, params=p).json()
        results.extend(body.get("results", []))
        total_pages = body.get("totalPages", 1)
        if page >= total_pages:
            break
        page += 1
    return results


def fetch_v2_transactions(client: httpx.Client, account_id: str, cap_pages: int = 20) -> list[dict]:
    """GET /v2/transactions — paginação por CURSOR (campo `next`, URL ou null).

    O /transactions v1 foi deprecado (HTTP 410). O v2 não aceita `pageSize`:
    seguimos o cursor `next` até esgotar.
    """
    results: list[dict] = []
    path: str = "/v2/transactions"
    params: dict | None = {"accountId": account_id}
    for _ in range(cap_pages):
        body = request(client, "GET", path, params=params).json()
        results.extend(body.get("results", []))
        nxt = body.get("next")
        if not nxt:
            break
        path = nxt.replace(BASE_URL, "")  # cursor já embutido na query
        params = None
    return results


def field_names(records: list[dict]) -> list[str]:
    keys: set[str] = set()
    for r in records[:50]:
        keys.update(r.keys())
    return sorted(keys)


def capture_item_data(client: httpx.Client, item_id: str) -> None:
    print(f"\n=== Captura de dados do item {item_id} ===")

    accounts = request(client, "GET", "/accounts", params={"itemId": item_id}).json().get("results", [])
    save("accounts", accounts)
    print(f"• contas: {len(accounts)}  campos={field_names(accounts)}")

    all_tx: list[dict] = []
    for acc in accounts:
        acc_id, subtype = acc["id"], acc.get("subtype")
        txs = fetch_v2_transactions(client, acc_id)
        all_tx.extend(txs)
        print(f"  - conta {subtype} {acc_id}: {len(txs)} transações")
        if acc.get("type") == "CREDIT":
            bills = request(client, "GET", "/bills", params={"accountId": acc_id}, allow_error=True)
            if bills.status_code < 400:
                b = bills.json().get("results", [])
                save(f"bills_{acc_id}", b)
                print(f"    faturas: {len(b)}  campos={field_names(b)}")
            else:
                print(f"    faturas: indisponível ({bills.status_code})")
    save("transactions", all_tx)
    print(f"• transações totais: {len(all_tx)}  campos={field_names(all_tx)}")

    investments = paginate(client, "/investments", {"itemId": item_id})
    save("investments", investments)
    print(f"• investimentos: {len(investments)}  campos={field_names(investments)}")
    for inv in investments[:3]:
        itx = request(
            client, "GET", f"/investments/{inv['id']}/transactions", allow_error=True
        )
        if itx.status_code < 400:
            data = itx.json().get("results", [])
            save(f"investment_transactions_{inv['id']}", data)
            print(f"  - inv {inv.get('type')} {inv['id']}: {len(data)} movimentos")


def capture_categories(client: httpx.Client) -> None:
    """Independe de item. Mapeia a taxonomia e sonda criação/regras."""
    print("\n=== Categorias (taxonomia do Pluggy) ===")
    cats = request(client, "GET", "/categories").json().get("results", [])
    save("categories", cats)
    roots = [c for c in cats if not c.get("parentId")]
    print(f"• categorias: {len(cats)} (raízes={len(roots)})  campos={field_names(cats)}")

    # Pergunta-chave: a API permite CRIAR categorias novas?
    print("→ sonda POST /categories (esperado falhar: taxonomia é fixa)")
    probe = request(
        client, "POST", "/categories",
        json_body={"description": "mango-probe"}, allow_error=True,
    )
    save("probe_post_categories", {"status": probe.status_code, "body": _safe_json(probe)})
    print(f"   resultado: HTTP {probe.status_code} → {probe.text[:200]}")

    # Mecanismo de override suportado: regras de categorização (NÃO cria categorias;
    # apenas mapeia transações para categorias EXISTENTES). Caminho: /categories/rules.
    rules = request(client, "GET", "/categories/rules", allow_error=True)
    save("category_rules", {"status": rules.status_code, "body": _safe_json(rules)})
    print(f"→ GET /categories/rules: HTTP {rules.status_code}")
    # Schema do POST (body vazio → erro de validação, não cria nada).
    rule_schema = request(client, "POST", "/categories/rules", json_body={}, allow_error=True)
    save("probe_post_categories_rules", {"status": rule_schema.status_code, "body": _safe_json(rule_schema)})
    print(f"→ POST /categories/rules (vazio): HTTP {rule_schema.status_code} → {rule_schema.text[:160]}")


def _safe_json(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return resp.text


def main() -> None:
    load_dotenv(SCRIPT_DIR / ".env")
    client_id = os.getenv("PLUGGY_CLIENT_ID")
    client_secret = os.getenv("PLUGGY_CLIENT_SECRET")
    if not client_id or not client_secret:
        fail(
            "Defina PLUGGY_CLIENT_ID e PLUGGY_CLIENT_SECRET.\n"
            "   cp scripts/discovery/.env.example scripts/discovery/.env  e preencha."
        )

    with httpx.Client(timeout=60) as client:
        api_key = authenticate(client, client_id, client_secret)
        client.headers["X-API-KEY"] = api_key

        # Categorias não dependem de um item conectado — capturamos sempre.
        capture_categories(client)

        item_id = os.getenv("PLUGGY_ITEM_ID")
        if item_id:
            print(f"\n→ usando PLUGGY_ITEM_ID do .env: {item_id}")
        else:
            connector_id = pick_sandbox_connector(client)
            item_id = create_item(client, connector_id)
            wait_for_item(client, item_id)

        capture_item_data(client, item_id)

    print(f"\n✓ Concluído. JSONs crus em: {RAW_DIR}")
    print("  Use-os para preencher docs/dev/descoberta-pluggy.md (excertos redigidos).")


if __name__ == "__main__":
    main()
