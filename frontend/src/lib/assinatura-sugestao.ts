/**
 * Sugestão de assinatura por semelhança de nome (§4.7).
 *
 * Descrições de banco vêm com prefixos/sufixos ("PAG*Netflix", "NETFLIX.COM AMSTERDAM"), então a
 * comparação é **híbrida**: normaliza (sem acento, minúsculas, espaços colapsados) e considera
 * parecido se um nome contém o outro (>= 4 chars, p/ evitar falso positivo) OU a razão de distância
 * de edição (Levenshtein) >= LIMIAR. Roda no cliente sobre as assinaturas já carregadas — sem custo
 * no servidor nem endpoint novo.
 */

export const LIMIAR = 0.82

export function normalizar(s: string): string {
  return s
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim()
}

/** Razão de similaridade por distância de edição: 1 = igual, 0 = nada em comum. */
export function ratioLevenshtein(a: string, b: string): number {
  if (a === b) return 1
  if (!a.length || !b.length) return 0
  const m = a.length
  const n = b.length
  let prev = Array.from({ length: n + 1 }, (_, j) => j)
  for (let i = 1; i <= m; i++) {
    const cur = [i]
    for (let j = 1; j <= n; j++) {
      const custo = a[i - 1] === b[j - 1] ? 0 : 1
      cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + custo)
    }
    prev = cur
  }
  return 1 - prev[n] / Math.max(m, n)
}

/** Pontua o quão parecidos são dois nomes já normalizados (contém = 1; senão a razão de edição). */
function pontuar(txNorm: string, nomeNorm: string): number {
  if (nomeNorm.length < 3) return 0
  if (
    nomeNorm.length >= 4 &&
    (txNorm.includes(nomeNorm) || nomeNorm.includes(txNorm))
  )
    return 1
  return ratioLevenshtein(txNorm, nomeNorm)
}

export type Sugestao = { id: number; nome: string }

type AssinaturaLike = {
  id: number
  nome: string
  nomes_transacao: string[]
}

/**
 * Melhor assinatura cujo nome ou aliases (`nomes_transacao`) se parecem com o texto da transação.
 * Retorna null se nada passar do LIMIAR.
 */
export function sugerir(
  texto: string | null | undefined,
  assinaturas: AssinaturaLike[]
): Sugestao | null {
  const txNorm = normalizar(texto ?? "")
  if (txNorm.length < 3) return null
  let melhor: { id: number; nome: string; score: number } | null = null
  for (const a of assinaturas) {
    for (const candidato of [a.nome, ...a.nomes_transacao]) {
      const score = pontuar(txNorm, normalizar(candidato))
      if (score >= LIMIAR && (!melhor || score > melhor.score)) {
        melhor = { id: a.id, nome: a.nome, score }
      }
    }
  }
  return melhor ? { id: melhor.id, nome: melhor.nome } : null
}
