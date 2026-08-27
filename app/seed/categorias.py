"""Seed idempotente da taxonomia de categorias do Pluggy (§4.5).

Escreve só as linhas GLOBAIS (`usuario_id` NULL) — as categorias personalizadas do usuário moram
na mesma tabela e nunca são tocadas aqui (o upsert é por `pluggy_id` do snapshot).

Lê o snapshot versionado `data/categories.json` (capturado na descoberta) e faz upsert por
`pluggy_id`. Raízes antes dos filhos (FK auto-referente `parent_id`). Idempotente: roda a
cada boot sem duplicar.
"""

import json
from pathlib import Path

from app.db.session import SessionLocal
from app.repositories.categoria import upsert_global

_DATA = Path(__file__).resolve().parent / "data" / "categories.json"


def seed_categorias() -> None:
    registros = json.loads(_DATA.read_text(encoding="utf-8"))
    # Raízes (sem parentId) primeiro p/ satisfazer a FK auto-referente.
    registros.sort(key=lambda c: (c.get("parentId") is not None, c["id"]))

    with SessionLocal() as db:
        for c in registros:
            upsert_global(
                db,
                c["id"],
                description=c["description"],
                description_translated=c.get("descriptionTranslated"),
                parent_id=c.get("parentId"),
            )
        db.commit()
