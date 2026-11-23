/**
 * Cor por categoria nos gráficos de despesa (dataviz): as 8 maiores do período levam os slots
 * categóricos em ordem fixa (nunca ciclados); da 9ª em diante caem em "Outras" (cor neutra).
 * A mesma atribuição vale para a rosca, as barras-legenda e o empilhado por período do card.
 *
 * ponytail: o slot segue o ranking do período, então trocar o período pode repintar uma
 * categoria. Cor fixa por entidade pediria uma ordem global por usuário — fazer se incomodar.
 */

export const SLOTS_CATEGORICOS = 8
export const ID_OUTRAS = "__outras__"
export const ID_SEM = "__sem__"
const SEM = ID_SEM

/** Fatia/linha que vira filtro de transações: uma categoria de verdade (nem "Outras", que junta
 *  várias, nem "Sem categoria", que a listagem não filtra). */
export const ehCategoriaReal = (id: string) => id !== ID_OUTRAS && id !== ID_SEM

export type GastoEntrada = {
  categoria_id: string | null
  total_centavos: number
}

export type ItemCategoria = {
  id: string
  nome: string
  valor: number
  /** 0..7 = slot da paleta; null = cai em "Outras". */
  slot: number | null
}

export type Distribuicao = {
  /** Todas as categorias com gasto > 0, maior primeiro (as barras-legenda). */
  itens: ItemCategoria[]
  /** Fatias da rosca: até 8 categorias + "Outras" (soma = total). */
  fatias: ItemCategoria[]
  /** id → slot (null = outras), para colorir o empilhado com a mesma regra. */
  slotDe: (categoriaId: string | null) => number | null
  total: number
}

export function distribuirCategorias(
  gastos: GastoEntrada[],
  rotulo: Map<string, string>
): Distribuicao {
  const somas = new Map<string, number>()
  for (const g of gastos) {
    const id = g.categoria_id ?? SEM
    somas.set(id, (somas.get(id) ?? 0) + g.total_centavos)
  }
  const ordenados = [...somas.entries()]
    .filter(([, v]) => v > 0)
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
  const slots = new Map(
    ordenados.slice(0, SLOTS_CATEGORICOS).map(([id], i) => [id, i])
  )
  const nome = (id: string) =>
    id === SEM ? "Sem categoria" : (rotulo.get(id) ?? id)

  const itens: ItemCategoria[] = ordenados.map(([id, valor]) => ({
    id,
    nome: nome(id),
    valor,
    slot: slots.get(id) ?? null,
  }))
  const resto = itens.filter((i) => i.slot === null)
  const fatias = itens.filter((i) => i.slot !== null)
  if (resto.length > 0) {
    fatias.push({
      id: ID_OUTRAS,
      nome: `Outras (${resto.length})`,
      valor: resto.reduce((s, i) => s + i.valor, 0),
      slot: null,
    })
  }
  return {
    itens,
    fatias,
    slotDe: (id) => slots.get(id ?? SEM) ?? null,
    total: itens.reduce((s, i) => s + i.valor, 0),
  }
}
