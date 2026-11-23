/** Só o que os helpers leem — aceita `Categoria` da API e dublês do self-check. */
type CategoriaArvore = { pluggy_id: string; parent_id?: string | null }

/** Categorias da aba Investimentos do orçamento: subárvore de 03 menos a de 0306 (juros e
 *  dividendos são receita). Espelha `categorias_investimento` do backend. */
export function categoriasDeInvestimento(
  categorias: CategoriaArvore[]
): Set<string> {
  const filhos = new Map<string, string[]>()
  for (const c of categorias)
    if (c.parent_id)
      filhos.set(c.parent_id, [...(filhos.get(c.parent_id) ?? []), c.pluggy_id])
  const subarvore = (raiz: string): Set<string> => {
    const vistos = new Set([raiz])
    const pilha = [raiz]
    while (pilha.length) {
      for (const f of filhos.get(pilha.pop()!) ?? []) {
        if (vistos.has(f)) continue
        vistos.add(f)
        pilha.push(f)
      }
    }
    return vistos
  }
  const rendimentos = subarvore("03060000")
  return new Set(
    [...subarvore("03000000")].filter((id) => !rendimentos.has(id))
  )
}

/** Ids que o seletor de categoria esconde num orçamento do tipo: investimento só aceita
 *  categorias de investimento; despesa/receita, as demais. */
export function excluidasDoTipo(
  categorias: CategoriaArvore[],
  tipo: "despesa" | "receita" | "investimento"
): string[] {
  const invest = categoriasDeInvestimento(categorias)
  return categorias
    .map((c) => c.pluggy_id)
    .filter((id) => invest.has(id) !== (tipo === "investimento"))
}
