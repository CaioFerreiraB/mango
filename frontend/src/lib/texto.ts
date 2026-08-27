/** Normalização de texto para busca/comparação no cliente.
 *
 * Espelha `app/services/texto.py::normalizar_texto` — minúsculo, sem acento, espaços colapsados.
 * Em pt-BR comparar com acento erra o caso mais comum ("Farmácia" vs. "farmacia").
 */
export function normalizarBusca(valor: string | null | undefined): string {
  return (valor ?? "")
    .normalize("NFKD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase()
    .trim()
    .split(/\s+/)
    .join(" ")
}
