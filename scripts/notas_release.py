"""Notas da página de release do GitHub a partir da seção da versão no CHANGELOG.

    uv run python scripts/notas_release.py 0.10.0 > /tmp/notas.md
    gh release create v0.10.0 --verify-tag --title "v0.10.0 — <tema>" --notes-file /tmp/notas.md

A seção sai sem a quebra de linha manual (a página de release renderiza cada quebra), com os links
relativos presos à tag e o rodapé da imagem + comparação com a versão anterior.
"""

import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
REPO = "https://github.com/CaioFerreiraB/mango"


def secoes() -> list[tuple[str, str]]:
    """[(versão, corpo)] do CHANGELOG, da mais nova para a mais antiga (sem "Não publicado")."""
    texto = (RAIZ / "CHANGELOG.md").read_text(encoding="utf-8").split("\n[Não publicado]:")[0]
    out = []
    for bloco in re.split(r"^## \[", texto, flags=re.M)[1:]:
        cabecalho, corpo = bloco.split("\n", 1)
        versao = cabecalho.split("]")[0]
        if versao != "Não publicado":
            out.append((versao, corpo.strip()))
    return out


def desquebrar(texto: str) -> str:
    """Junta as linhas de continuação de parágrafos e itens de lista."""
    out: list[str] = []
    for linha in texto.split("\n"):
        anterior = out[-1] if out else ""
        if (
            anterior.strip()
            and linha.strip()
            and not re.match(r"\s*(#|- |\* |\d+\. |\||```|>)", linha)
            and not anterior.lstrip().startswith(("#", "|", "```"))
        ):
            out[-1] = anterior.rstrip() + " " + linha.strip()
        else:
            out.append(linha)
    return "\n".join(out)


def notas(versao: str) -> str:
    todas = secoes()
    versoes = [v for v, _ in todas]
    if versao not in versoes:
        sys.exit(f"erro: versão {versao} não está no CHANGELOG")
    i = versoes.index(versao)
    tag, anterior = f"v{versao}", versoes[i + 1] if i + 1 < len(versoes) else None
    corpo = re.sub(
        r"\]\((?!https?://|#)([^)]+)\)", rf"]({REPO}/blob/{tag}/\1)", desquebrar(todas[i][1])
    )
    imagem = f"Imagem multi-arch: `ghcr.io/caioferreirab/mango:{versao}`."
    instrucoes = f"Instruções em [deploy/README.md]({REPO}/blob/{tag}/deploy/README.md)."
    if anterior is None:
        rodape = f"### Instalação\n\n{imagem} {instrucoes}"
        rodape += f"\n\n**Primeira versão publicada:** [{tag}]({REPO}/tree/{tag})"
    else:
        rodape = (
            f"### Atualização\n\n{imagem} Faça backup antes de atualizar; as migrations rodam "
            f"sozinhas no boot do container. {instrucoes}\n\n**Mudanças completas:** "
            f"[v{anterior}...{tag}]({REPO}/compare/v{anterior}...{tag})"
        )
    return f"{corpo}\n\n{rodape}\n"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("uso: notas_release.py X.Y.Z")
    sys.stdout.write(notas(sys.argv[1]))
