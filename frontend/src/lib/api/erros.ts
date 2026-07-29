/** Extrai o `detail` de um erro do backend (FastAPI), com fallback amigável. */
export function mensagemErro(error: unknown, fallback: string): string {
  if (error && typeof error === "object" && "detail" in error) {
    const d = (error as { detail?: unknown }).detail
    if (typeof d === "string") return d
  }
  return fallback
}
