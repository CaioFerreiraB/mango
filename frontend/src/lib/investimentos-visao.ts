/**
 * Agregações puras dos gráficos da Visão Geral de investimentos (sem React): fecho mensal da série
 * da carteira, matriz mês × ano de rentabilidade vs CDI e vencimentos de renda fixa por mês.
 * Self-check: `npx tsx src/lib/investimentos-visao.check.ts`.
 */

export type PontoSerie = {
  data: string
  valor_centavos: number
  investido_centavos: number
}

/** Último ponto de cada mês (`yyyy-mm`), em ordem. Mês sem aporte conhecido (investido 0 com
 *  patrimônio > 0 — a série devolve 0 quando o custo é desconhecido) sai com `investido` nulo:
 *  sem isso toda a carteira apareceria como "valorização". */
export function fechamentosMensais(
  pontos: PontoSerie[]
): { mes: string; valor: number; investido: number | null }[] {
  const porMes = new Map<string, PontoSerie>()
  for (const p of [...pontos].sort((a, b) => a.data.localeCompare(b.data)))
    porMes.set(p.data.slice(0, 7), p)
  return [...porMes].map(([mes, p]) => ({
    mes,
    valor: p.valor_centavos,
    investido:
      p.investido_centavos === 0 && p.valor_centavos > 0
        ? null
        : p.investido_centavos,
  }))
}

/** Corta os pontos do começo em que o recorte ainda não tinha posição (valor 0): sem patrimônio
 *  não há retorno, e eles virariam meses de "0,0%" no mapa (a série de renda variável cobre a janela
 *  inteira pedida, zerada antes da 1ª compra). */
export function aPartirDaPrimeiraPosicao<T extends { valor_centavos: number }>(
  pontos: T[]
): T[] {
  const i = pontos.findIndex((p) => p.valor_centavos > 0)
  return i < 0 ? [] : pontos.slice(i)
}

export type LinhaAno = {
  ano: number
  /** Retorno de cada mês (jan…dez), `null` fora da série. */
  meses: (number | null)[]
  cdi: (number | null)[]
  /** Composto dos meses disponíveis do ano (`null` sem nenhum). */
  total: number | null
  totalCdi: number | null
}

const compor = (pcts: (number | null)[]): number | null => {
  const v = pcts.filter((p): p is number => p != null)
  return v.length
    ? (v.reduce((acc, p) => acc * (1 + p / 100), 1) - 1) * 100
    : null
}

/** Matriz ano × mês (anos do mais recente ao mais antigo). O CDI do ano compõe só os meses em que
 *  a carteira tem retorno — comparação no mesmo período. */
export function matrizRentabilidade(
  carteira: { mes: string; pct: number }[],
  cdi: { mes: string; pct: number }[]
): LinhaAno[] {
  const cdiMes = new Map(cdi.map((c) => [c.mes, c.pct]))
  const anos = new Map<number, LinhaAno>()
  for (const { mes, pct } of carteira) {
    const [a, m] = mes.split("-").map(Number)
    const linha = anos.get(a!) ?? {
      ano: a!,
      meses: Array<number | null>(12).fill(null),
      cdi: Array<number | null>(12).fill(null),
      total: null,
      totalCdi: null,
    }
    linha.meses[m! - 1] = pct
    linha.cdi[m! - 1] = cdiMes.get(mes) ?? null
    anos.set(a!, linha)
  }
  return [...anos.values()]
    .map((l) => ({ ...l, total: compor(l.meses), totalCdi: compor(l.cdi) }))
    .sort((x, y) => y.ano - x.ano)
}

export type ItemVencimento = {
  id: number
  nome: string | null
  valor_centavos: number
  due_date?: string | null
}

/** Vencimentos de hoje em diante agrupados por mês (`yyyy-mm`), do mais próximo ao mais distante. */
export function vencimentosPorMes(
  itens: ItemVencimento[],
  hoje: string
): { mes: string; total: number; itens: ItemVencimento[] }[] {
  const grupos = new Map<string, ItemVencimento[]>()
  for (const it of itens) {
    const dia = it.due_date?.slice(0, 10)
    if (!dia || dia < hoje) continue
    const mes = dia.slice(0, 7)
    grupos.set(mes, [...(grupos.get(mes) ?? []), it])
  }
  return [...grupos]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([mes, lista]) => ({
      mes,
      total: lista.reduce((s, i) => s + i.valor_centavos, 0),
      itens: [...lista].sort((a, b) =>
        (a.due_date ?? "").localeCompare(b.due_date ?? "")
      ),
    }))
}
