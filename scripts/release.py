"""Prepara uma versão: sincroniza os arquivos de versão, fecha o CHANGELOG, commita e cria a tag.

    make release v=0.2.0

A versão vive em quatro lugares (pyproject, app/__init__, package.json e package-lock). Manter isso
à mão garante divergência — daí o script. Ele não empurra nada: revise `git show` e só então
`git push origin main --follow-tags`, que é o que dispara o workflow de release.
"""

import datetime as dt
import pathlib
import re
import subprocess
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
REPO = "https://github.com/CaioFerreiraB/mango"


def erro(msg: str) -> None:
    print(f"erro: {msg}", file=sys.stderr)
    sys.exit(1)


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=RAIZ, capture_output=True, text=True, check=True
    ).stdout.strip()


ARQUIVOS_DE_VERSAO = (
    "pyproject.toml",
    "app/__init__.py",
    "frontend/package.json",
    "frontend/package-lock.json",
    "uv.lock",
    "CHANGELOG.md",
)


def versao_atual() -> str:
    achado = re.search(r'__version__ = "([^"]+)"', (RAIZ / "app/__init__.py").read_text("utf-8"))
    if not achado:
        erro("não consegui ler __version__ de app/__init__.py")
    return achado.group(1)


def substituir(caminho: str, padrao: str, novo: str) -> tuple[str, str]:
    """Calcula (sem gravar) o novo conteúdo do arquivo. Ver `gravar`."""
    texto = (RAIZ / caminho).read_text(encoding="utf-8")
    texto_novo, trocas = re.subn(padrao, novo, texto, count=1, flags=re.MULTILINE)
    if trocas != 1:
        erro(f"não encontrei a linha de versão em {caminho} (padrão: {padrao})")
    return caminho, texto_novo


def gravar(edicoes: list[tuple[str, str]]) -> None:
    """Grava tudo de uma vez, só depois de todos os arquivos terem casado.

    Se um padrão não bater, `substituir` aborta antes de qualquer escrita — não existe estado
    intermediário com metade dos arquivos na versão nova.
    """
    for caminho, texto in edicoes:
        (RAIZ / caminho).write_text(texto, encoding="utf-8")


def substituir_no_lock(antiga: str, nova: str) -> tuple[str, str]:
    """Bump do package-lock.json, que repete a versão do projeto em dois lugares.

    Uma no topo e outra no nó raiz de `packages` (`""`), ambas no começo do arquivo. Trocamos por
    literal e só no cabeçalho: um regex de versão solto casaria com a primeira dependência que
    tivesse o mesmo número.
    """
    caminho = "frontend/package-lock.json"
    linhas = (RAIZ / caminho).read_text(encoding="utf-8").split("\n")
    cabecalho, resto = linhas[:15], linhas[15:]
    alvo, trocado = f'"version": "{antiga}"', f'"version": "{nova}"'
    trocas = sum(alvo in linha for linha in cabecalho)
    if trocas != 2:
        erro(f"esperava 2 ocorrências de {alvo} no início do package-lock.json, achei {trocas}")
    cabecalho = [linha.replace(alvo, trocado) for linha in cabecalho]
    return caminho, "\n".join([*cabecalho, *resto])


def fechar_changelog(versao: str, hoje: str) -> None:
    """Converte a seção `[Não publicado]` na seção da versão e recria os links de comparação."""
    arquivo = RAIZ / "CHANGELOG.md"
    texto = arquivo.read_text(encoding="utf-8")

    corpo = texto.split("## [Não publicado]", 1)
    if len(corpo) != 2:
        erro("CHANGELOG.md não tem a seção '## [Não publicado]'")
    novas_entradas = corpo[1].split("\n## ", 1)[0].strip()
    if not novas_entradas:
        erro("nada em '## [Não publicado]' — descreva as mudanças antes de publicar")

    texto = texto.replace(
        "## [Não publicado]",
        f"## [Não publicado]\n\n## [{versao}] — {hoje}",
        1,
    )
    anterior = ultima_tag()
    texto = re.sub(
        r"\[Não publicado\]: \S+",
        f"[Não publicado]: {REPO}/compare/v{versao}...HEAD",
        texto,
        count=1,
    )
    link_novo = (
        f"[{versao}]: {REPO}/compare/{anterior}...v{versao}"
        if anterior
        else f"[{versao}]: {REPO}/releases/tag/v{versao}"
    )
    texto = texto.replace("\n[Não publicado]: ", f"\n{link_novo}\n[Não publicado]: ", 1)
    # Reordena: o link de "Não publicado" fica no topo da lista, seguido das versões.
    linhas = texto.rstrip().split("\n")
    links = [ln for ln in linhas if re.match(r"^\[[^\]]+\]: https?://", ln)]
    resto = linhas[: len(linhas) - len(links)]
    links.sort(key=lambda ln: ln.startswith("[Não publicado]"), reverse=True)
    arquivo.write_text("\n".join([*resto, *links]) + "\n", encoding="utf-8")


def ultima_tag() -> str | None:
    try:
        return git("describe", "--tags", "--abbrev=0", "--match", "v*")
    except subprocess.CalledProcessError:
        return None


def main() -> None:
    if len(sys.argv) != 2:
        erro("uso: make release v=X.Y.Z")
    versao = sys.argv[1].lstrip("v")
    if not re.fullmatch(r"\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?", versao):
        erro(f"versão inválida: {versao!r} — use SemVer, ex.: 0.2.0 ou 0.2.0-rc1")

    if git("status", "--porcelain"):
        erro("há mudanças não commitadas — publique a partir de uma árvore limpa")
    if f"v{versao}" in git("tag", "--list", f"v{versao}"):
        erro(f"a tag v{versao} já existe")

    hoje = dt.date.today().isoformat()
    antiga = versao_atual()
    gravar(
        [
            substituir("pyproject.toml", r'^version = "[^"]+"', f'version = "{versao}"'),
            substituir("app/__init__.py", r'__version__ = "[^"]+"', f'__version__ = "{versao}"'),
            substituir("frontend/package.json", r'"version": "[^"]+"', f'"version": "{versao}"'),
            # O uv.lock guarda a versão do próprio projeto. Sem bumpar aqui, o primeiro `uv run`
            # depois da release reescreve o arquivo e suja a árvore — o que faz a release seguinte
            # abortar por "mudanças não commitadas". Ancorado no pacote `mango` para não pegar a
            # versão de uma dependência.
            substituir("uv.lock", r'(name = "mango"\nversion = )"[^"]+"', rf'\g<1>"{versao}"'),
            substituir_no_lock(antiga, versao),
        ]
    )
    fechar_changelog(versao, hoje)

    # Só os arquivos que o script tocou: um `add -A` arrastaria qualquer arquivo não rastreado
    # da árvore para dentro da release.
    git("add", *ARQUIVOS_DE_VERSAO)
    git("commit", "-m", f"release v{versao}")
    git("tag", "-a", f"v{versao}", "-m", f"v{versao}")
    print(
        f"v{versao} preparada.\n"
        f"  revise:   git show v{versao}\n"
        f"  publique: git push origin main --follow-tags"
    )


if __name__ == "__main__":
    main()
