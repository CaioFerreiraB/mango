"""Normalização de texto para comparação (§4.5).

Usada em dois lugares que precisam casar exatamente do mesmo jeito: a unicidade do nome de uma
categoria personalizada e o casamento das regras de categorização. Como o vocabulário é pt-BR,
comparar sem remover acento erraria o caso mais comum ("Farmácia" vs. "farmacia").

NÃO confundir com `assinatura_deteccao.normalizar_nome`, que só faz minúsculo + colapso de espaço:
aquela define o casamento de aliases de assinatura e mudá-la alteraria vínculos já existentes.
"""

import unicodedata


def normalizar_texto(valor: str | None) -> str:
    """Minúsculo, sem acento, espaços colapsados. `None`/vazio → `""`."""
    sem_acento = unicodedata.normalize("NFKD", (valor or "").strip())
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return " ".join(sem_acento.lower().split())
