/**
 * Layout personalizável do dashboard: catálogo de widgets das três abas (fonte única dos ids e dos
 * padrões) e o merge com o que o usuário salvou no perfil (`dashboard_layout`). As abas dividem a
 * mesma lista salva — cada uma lê os seus ids (prefixo `rec-`/`desp-`; o resto é da Geral) e a
 * ordem relativa entre eles.
 */

/** Colunas de um grid de 60 (divisível por 6, 5, 4 e 3). */
export type Largura = number

/** `altura` em px (mínima do card, só em telas largas); ausente = altura do conteúdo. */
export type WidgetLayout = {
  id: string
  largura: Largura
  altura?: number
  visivel: boolean
}

export type Aba = "geral" | "receitas" | "despesas"

export type WidgetId =
  | "kpi-saldo"
  | "kpi-entradas"
  | "kpi-saidas"
  | "kpi-resultado"
  | "kpi-investido"
  | "despesas-fixas"
  | "despesas-fixas-proximos"
  | "ultimas"
  | "fluxo"
  | "calendario"
  | "patrimonio"
  | "rec-total"
  | "rec-anterior"
  | "rec-media"
  | "rec-previsto"
  | "rec-evolucao"
  | "rec-categorias"
  | "rec-fontes"
  | "rec-previstas"
  | "rec-acumulado"
  | "desp-total"
  | "desp-anterior"
  | "desp-media"
  | "desp-orcamento"
  | "desp-evolucao"
  | "desp-categorias"
  | "desp-maiores"
  | "desp-orcamento-categorias"
  | "desp-acumulado"
  | "desp-dia-semana"
  | "desp-meios"
  | "desp-cartoes"

type ItemCatalogo = {
  id: WidgetId
  titulo: string
  largura: Largura
  /** KPI: no celular fica dois por linha (o resto ocupa a linha toda). */
  compacto?: boolean
}

/** Ordem e largura padrão (grid de 60 colunas em telas largas). */
export const CATALOGO: ItemCatalogo[] = [
  // Geral — herói (saldo com a curva de 30 dias) na linha inteira; os quatro fluxos do mês em ¼.
  { id: "kpi-saldo", titulo: "Saldo em contas", largura: 60 },
  {
    id: "kpi-entradas",
    titulo: "Entradas no mês",
    largura: 15,
    compacto: true,
  },
  { id: "kpi-saidas", titulo: "Saídas no mês", largura: 15, compacto: true },
  {
    id: "kpi-resultado",
    titulo: "Resultado no mês",
    largura: 15,
    compacto: true,
  },
  {
    id: "kpi-investido",
    titulo: "Investido no mês",
    largura: 15,
    compacto: true,
  },
  { id: "despesas-fixas", titulo: "Despesas fixas · visão geral", largura: 30 },
  {
    id: "despesas-fixas-proximos",
    titulo: "Despesas fixas · lista",
    largura: 30,
  },
  { id: "ultimas", titulo: "Últimas transações", largura: 60 },
  { id: "fluxo", titulo: "Entradas e saídas", largura: 60 },
  { id: "calendario", titulo: "Calendário do mês", largura: 60 },
  { id: "patrimonio", titulo: "Evolução patrimonial", largura: 60 },
  // Receitas
  {
    id: "rec-total",
    titulo: "Recebido no período",
    largura: 15,
    compacto: true,
  },
  {
    id: "rec-anterior",
    titulo: "Período anterior",
    largura: 15,
    compacto: true,
  },
  {
    id: "rec-media",
    titulo: "Média por recebimento",
    largura: 15,
    compacto: true,
  },
  {
    id: "rec-previsto",
    titulo: "Previsto (orçamento)",
    largura: 15,
    compacto: true,
  },
  { id: "rec-evolucao", titulo: "Evolução das receitas", largura: 60 },
  { id: "rec-categorias", titulo: "Receitas por categoria", largura: 30 },
  { id: "rec-fontes", titulo: "Principais fontes de receita", largura: 30 },
  { id: "rec-previstas", titulo: "Previstas × realizadas", largura: 30 },
  { id: "rec-acumulado", titulo: "Receitas acumuladas", largura: 30 },
  // Despesas
  { id: "desp-total", titulo: "Gasto no período", largura: 15, compacto: true },
  {
    id: "desp-anterior",
    titulo: "Período anterior",
    largura: 15,
    compacto: true,
  },
  { id: "desp-media", titulo: "Média diária", largura: 15, compacto: true },
  { id: "desp-orcamento", titulo: "Orçamento", largura: 15, compacto: true },
  { id: "desp-evolucao", titulo: "Evolução das despesas", largura: 60 },
  { id: "desp-categorias", titulo: "Despesas por categoria", largura: 30 },
  { id: "desp-maiores", titulo: "Maiores despesas", largura: 30 },
  {
    id: "desp-orcamento-categorias",
    titulo: "Orçamento por categoria",
    largura: 30,
  },
  { id: "desp-acumulado", titulo: "Despesas acumuladas", largura: 30 },
  { id: "desp-dia-semana", titulo: "Despesas por dia da semana", largura: 30 },
  { id: "desp-meios", titulo: "Por meio de pagamento", largura: 30 },
  { id: "desp-cartoes", titulo: "Cartões de crédito", largura: 60 },
]
// Ids antigos ("categorias", "faturas") num layout salvo caem no merge como desconhecidos.

const POR_ID = new Map(CATALOGO.map((w) => [w.id as string, w]))

export function abaDe(id: string): Aba {
  if (id.startsWith("rec-")) return "receitas"
  if (id.startsWith("desp-")) return "despesas"
  return "geral"
}

export const ehCompacto = (id: string) => Boolean(POR_ID.get(id)?.compacto)

/** Larguras em que a borda arrastada encaixa: frações "redondas" de 60. */
export const LARGURAS: Largura[] = [
  10, 12, 15, 20, 24, 30, 36, 40, 45, 48, 50, 60,
]

export const ROTULO_LARGURA: Record<number, string> = {
  10: "⅙",
  12: "⅕",
  15: "¼",
  20: "⅓",
  24: "⅖",
  30: "½",
  36: "⅗",
  40: "⅔",
  45: "¾",
  48: "⅘",
  50: "⅚",
  60: "inteira",
}

export const ALTURA_MIN = 96
export const ALTURA_MAX = 1600

/** Largura permitida mais próxima de `colunas` (de 60). */
export function encaixarLargura(colunas: number): Largura {
  return LARGURAS.reduce((melhor, l) =>
    Math.abs(l - colunas) < Math.abs(melhor - colunas) ? l : melhor
  )
}

/** Altura em passos de 8px, dentro dos limites. */
export function encaixarAltura(px: number): number {
  return Math.min(ALTURA_MAX, Math.max(ALTURA_MIN, Math.round(px / 8) * 8))
}

/** Largura vizinha (teclado: ← encolhe, → alarga), parando nas bordas. */
export function passoLargura(l: Largura, delta: -1 | 1): Largura {
  const i = LARGURAS.indexOf(encaixarLargura(l))
  return LARGURAS[Math.min(LARGURAS.length - 1, Math.max(0, i + delta))]
}

const padraoDe = (w: ItemCatalogo): WidgetLayout => ({
  id: w.id,
  largura: w.largura,
  visivel: true,
})

export function layoutPadrao(): WidgetLayout[] {
  return CATALOGO.map(padraoDe)
}

/** Volta só a aba `aba` ao padrão; as outras ficam como estão. */
export function restaurarAba(layout: WidgetLayout[], aba: Aba): WidgetLayout[] {
  return [
    ...layout.filter((w) => abaDe(w.id) !== aba),
    ...layoutPadrao().filter((w) => abaDe(w.id) === aba),
  ]
}

/**
 * Layout efetivo: o salvo, na ordem salva, sem ids que o catálogo não conhece mais (widget
 * removido numa versão nova) nem repetidos; widget do catálogo ausente do salvo (widget novo)
 * entra visível, com a largura padrão, logo depois do vizinho anterior no catálogo (ou no início,
 * se nenhum anterior estiver no salvo). Largura fora das permitidas vira a padrão; altura fora
 * dos limites some (volta à do conteúdo). Sem salvo → padrão.
 */
export function mesclarLayout(
  salvo: WidgetLayout[] | null | undefined
): WidgetLayout[] {
  if (!salvo) return layoutPadrao()
  const vistos = new Set<string>()
  const out: WidgetLayout[] = []
  for (const w of salvo) {
    const cat = POR_ID.get(w.id)
    if (!cat || vistos.has(w.id)) continue
    vistos.add(w.id)
    const altura =
      typeof w.altura === "number" &&
      w.altura >= ALTURA_MIN &&
      w.altura <= ALTURA_MAX
        ? w.altura
        : undefined
    out.push({
      id: w.id,
      largura: LARGURAS.includes(w.largura) ? w.largura : cat.largura,
      ...(altura ? { altura } : {}),
      visivel: w.visivel,
    })
  }
  CATALOGO.forEach((w, i) => {
    if (vistos.has(w.id)) return
    let pos = 0
    for (let j = i - 1; j >= 0; j--) {
      const k = out.findIndex((x) => x.id === CATALOGO[j].id)
      if (k >= 0) {
        pos = k + 1
        break
      }
    }
    out.splice(pos, 0, padraoDe(w))
  })
  return out
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

/** Mesma configuração (a ordem entre abas diferentes não importa: cada aba lê só os seus). */
export function mesmoLayout(a: WidgetLayout[], b: WidgetLayout[]): boolean {
  const chave = (l: WidgetLayout[]) =>
    (["geral", "receitas", "despesas"] as const)
      .map((aba) => JSON.stringify(l.filter((w) => abaDe(w.id) === aba)))
      .join("|")
  return chave(a) === chave(b)
}
