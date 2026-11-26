/**
 * Calendário de calor do dashboard: escala divergente contínua (framboesa `--negative` no valor mais
 * negativo → superfície no zero → azul `--positive` no mais positivo) e texto legível em cima.
 * Funções puras sobre cores já resolvidas pelo tema (`rgba(r,g,b,a)` de `useTemaGrafico`).
 */

type RGB = [number, number, number]

function rgb(cor: string): RGB {
  const m = cor.match(/[\d.]+/g)
  if (!m || m.length < 3) throw new Error(`cor inválida: ${cor}`)
  return [Number(m[0]), Number(m[1]), Number(m[2])]
}

/** Mistura em sRGB — a mesma interpolação de um `linear-gradient` (a legenda bate com as células). */
export function misturar(base: string, alvo: string, peso: number): string {
  const a = rgb(base)
  const b = rgb(alvo)
  const c = a.map((x, i) => Math.round(x + (b[i] - x) * peso))
  return `rgb(${c[0]},${c[1]},${c[2]})`
}

function luminancia(cor: string): number {
  const [r, g, b] = rgb(cor).map((v) => {
    const s = v / 255
    return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

/** Razão de contraste WCAG 2. */
export function contraste(a: string, b: string): number {
  const [x, y] = [luminancia(a), luminancia(b)].sort((p, q) => q - p)
  return (x + 0.05) / (y + 0.05)
}

/**
 * Texto sobre o fundo: a primeira candidata com AA (4.5:1); nenhuma → a de maior contraste. Passe a
 * tinta do tema primeiro e preto/branco puros no fim: na faixa média da escala (L ~0.6) nem a tinta
 * slate nem a cor do card chegam a 4.5:1, mas preto ou branco sempre chegam (≥ 4.58:1).
 */
export function corTexto(fundo: string, candidatas: string[]): string {
  return (
    candidatas.find((c) => contraste(c, fundo) >= 4.5) ??
    candidatas.reduce((m, c) =>
      contraste(c, fundo) > contraste(m, fundo) ? c : m
    )
  )
}

/**
 * Posição do valor na escala, em [-1, 1]. Cada lado normaliza pelo seu extremo do mês (um salário
 * não desbota todas as despesas). Valor ≠ 0 tem piso de 0.12 para não sumir na superfície.
 */
/** Tom mínimo de um valor ≠ 0 (fração da cor cheia misturada à superfície). */
export const PISO = 0.12

export function intensidade(
  valor: number,
  maxPos: number,
  maxNeg: number
): number {
  if (valor === 0) return 0
  const ref = valor > 0 ? maxPos : maxNeg
  const t = ref > 0 ? Math.min(Math.abs(valor) / ref, 1) : 1
  return Math.sign(valor) * (PISO + (1 - PISO) * t)
}

/** Semanas do mês (domingo primeiro), com `null` nas casas fora do mês. `mes` é 1–12. */
export function semanasDoMes(ano: number, mes: number): (string | null)[][] {
  const dias = new Date(Date.UTC(ano, mes, 0)).getUTCDate()
  const offset = new Date(Date.UTC(ano, mes - 1, 1)).getUTCDay()
  const casas: (string | null)[] = Array(offset).fill(null)
  for (let d = 1; d <= dias; d++)
    casas.push(
      `${ano}-${String(mes).padStart(2, "0")}-${String(d).padStart(2, "0")}`
    )
  while (casas.length % 7) casas.push(null)
  return Array.from({ length: casas.length / 7 }, (_, i) =>
    casas.slice(i * 7, i * 7 + 7)
  )
}
