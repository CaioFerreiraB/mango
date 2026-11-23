/**
 * Layout personalizável do dashboard: catálogo de widgets (fonte única dos ids e dos padrões) e
 * o merge com o que o usuário salvou no perfil (`dashboard_layout`).
 */

/** Colunas de um grid de 60 (divisível por 5, 4 e 3): ⅕ ¼ ⅓ ½ ⅔ ¾ inteira. */
export type Largura = 12 | 15 | 20 | 30 | 40 | 45 | 60

export type WidgetLayout = { id: string; largura: Largura; visivel: boolean }

export type WidgetId =
  | "kpi-saldo"
  | "kpi-entradas"
  | "kpi-saidas"
  | "kpi-resultado"
  | "kpi-investido"
  | "fluxo"
  | "categorias"
  | "patrimonio"
  | "faturas"

/** Ordem e largura padrão (grid de 60 colunas a partir de `lg`). */
export const CATALOGO: { id: WidgetId; titulo: string; largura: Largura }[] = [
  { id: "kpi-saldo", titulo: "Saldo em contas", largura: 12 },
  { id: "kpi-entradas", titulo: "Entradas no mês", largura: 12 },
  { id: "kpi-saidas", titulo: "Saídas no mês", largura: 12 },
  { id: "kpi-resultado", titulo: "Resultado no mês", largura: 12 },
  { id: "kpi-investido", titulo: "Investido no mês", largura: 12 },
  { id: "fluxo", titulo: "Entradas e saídas", largura: 60 },
  { id: "categorias", titulo: "Despesas por categoria", largura: 60 },
  { id: "patrimonio", titulo: "Evolução patrimonial", largura: 60 },
  { id: "faturas", titulo: "Cartões de crédito", largura: 60 },
]

export const LARGURAS: Largura[] = [12, 15, 20, 30, 40, 45, 60]

export const ROTULO_LARGURA: Record<Largura, string> = {
  12: "⅕",
  15: "¼",
  20: "⅓",
  30: "½",
  40: "⅔",
  45: "¾",
  60: "inteira",
}

export function layoutPadrao(): WidgetLayout[] {
  return CATALOGO.map((w) => ({ id: w.id, largura: w.largura, visivel: true }))
}

/**
 * Layout efetivo: o salvo, na ordem salva, sem ids que o catálogo não conhece mais (widget
 * removido numa versão nova) nem repetidos; widget do catálogo ausente do salvo (widget novo)
 * entra no fim, visível, com a largura padrão. Sem salvo → padrão.
 */
export function mesclarLayout(
  salvo: WidgetLayout[] | null | undefined
): WidgetLayout[] {
  if (!salvo) return layoutPadrao()
  const conhecidos = new Set<string>(CATALOGO.map((w) => w.id))
  const vistos = new Set<string>()
  const out: WidgetLayout[] = []
  for (const w of salvo) {
    if (!conhecidos.has(w.id) || vistos.has(w.id)) continue
    vistos.add(w.id)
    out.push({
      id: w.id,
      largura: LARGURAS.includes(w.largura) ? w.largura : 60,
      visivel: w.visivel,
    })
  }
  for (const w of CATALOGO)
    if (!vistos.has(w.id))
      out.push({ id: w.id, largura: w.largura, visivel: true })
  return out
}

/** Próxima largura do ciclo ⅕ → ¼ → ⅓ → ½ → ⅔ → ¾ → inteira → ⅕. */
export function proximaLargura(l: Largura): Largura {
  return LARGURAS[(LARGURAS.indexOf(l) + 1) % LARGURAS.length]
}

/** Move o item `i` em `delta` posições (limitado às bordas). */
export function mover<T>(lista: T[], i: number, delta: number): T[] {
  const j = Math.min(Math.max(i + delta, 0), lista.length - 1)
  if (i === j) return lista
  const copia = [...lista]
  const [item] = copia.splice(i, 1)
  copia.splice(j, 0, item)
  return copia
}

export function mesmoLayout(a: WidgetLayout[], b: WidgetLayout[]): boolean {
  return JSON.stringify(a) === JSON.stringify(b)
}
