/**
 * Agregação das negociações (compras/vendas) de uma posição — consumido pela aba Movimentações do
 * drawer de FII. Puro (sem React), para ser testável: veja `investimento-negociacoes.check.ts`.
 *
 * Janela dos cards e do gráfico = os **12 meses-calendário** que terminam no mês corrente (SP), não
 * um recorte de 365 dias — assim card e barra somam exatamente o mesmo conjunto. A tabela lista o
 * histórico completo de BUY/SELL (sem recorte de janela).
 */
import type { InvestimentoTransacao } from "@/lib/api/investimentos"
import { formatBucketLabel, mesISO } from "@/lib/format"

export type LadoNegociacao = "BUY" | "SELL"

/** Total de um lado no período: quantidade (cotas) + valor em centavos. */
export type TotalLado = { qtd: number; valor: number }

/** Uma barra do gráfico de compras (um mês-calendário). `valor` em centavos, `qtd` em cotas. */
export type BucketCompra = { mes: string; label: string; valor: number; qtd: number }

/** Linha da tabela de negociações (já normalizada p/ exibição). */
export type Negociacao = {
  id: number
  lado: LadoNegociacao
  quando: string | null // data original (ISO) p/ formatDate; null quando sem data
  quantidade: number
  precoCentavos: number | null
  valorCentavos: number
  manual: boolean
}

export type AgregadoNegociacoes = {
  compras12m: TotalLado
  vendas12m: TotalLado
  buckets: BucketCompra[] // 12 meses fixos, ordem crescente (compras por mês)
  negociacoes: Negociacao[] // BUY/SELL, ordem de entrada preservada (a API já vem date DESC)
}

const num = (v: string | null | undefined) => (v == null ? 0 : Number(v))

/** Preço unitário da cota em centavos: `value_unitario` (reais) ou, na falta, valor total ÷ qtd. */
export function precoCotaCentavos(m: InvestimentoTransacao): number | null {
  if (m.value_unitario != null) return Math.round(Number(m.value_unitario) * 100)
  const q = num(m.quantity)
  return q > 0 ? Math.round(m.amount_centavos / q) : null
}

/** Últimos `n` meses (`yyyy-mm`) terminando em `mesAtual` (`yyyy-mm`), crescente. Aritmética
 *  inteira sobre ano·12+mês — sem `Date`, então imune ao off-by-one de fuso. */
export function ultimosMeses(mesAtual: string, n: number): string[] {
  const [a, m] = mesAtual.split("-").map(Number)
  const base = a * 12 + (m - 1)
  return Array.from({ length: n }, (_, i) => {
    const t = base - (n - 1 - i)
    return `${Math.floor(t / 12)}-${String((t % 12) + 1).padStart(2, "0")}`
  })
}

/** Mês SP (`yyyy-mm`) de um movimento, a partir do timestamp original (não do dia fatiado, que
 *  viraria meia-noite UTC e escorregaria de mês no fuso SP). `null` quando sem data. */
function mesDoMovimento(m: InvestimentoTransacao): string | null {
  const quando = m.date ?? m.trade_date
  return quando ? mesISO(quando) : null
}

/**
 * @param hoje data SP corrente `yyyy-mm-dd` (de `hojeISO()`) — injetada p/ ficar determinístico.
 */
export function agregarNegociacoes(
  transacoes: InvestimentoTransacao[],
  hoje: string
): AgregadoNegociacoes {
  const chaves = ultimosMeses(hoje.slice(0, 7), 12)
  const buckets = new Map<string, BucketCompra>(
    chaves.map((k) => [k, { mes: k, label: formatBucketLabel(`${k}-01`, "mensal"), valor: 0, qtd: 0 }])
  )
  const janela = new Set(chaves)

  const compras12m: TotalLado = { qtd: 0, valor: 0 }
  const vendas12m: TotalLado = { qtd: 0, valor: 0 }
  const negociacoes: Negociacao[] = []

  for (const m of transacoes) {
    const tipo = (m.type ?? "").toUpperCase()
    if (tipo !== "BUY" && tipo !== "SELL") continue // só negociações (proventos → aba Dividendos)

    const qtd = num(m.quantity)
    negociacoes.push({
      id: m.id,
      lado: tipo,
      quando: m.date ?? m.trade_date ?? null,
      quantidade: qtd,
      precoCentavos: precoCotaCentavos(m),
      valorCentavos: m.amount_centavos,
      manual: m.manual,
    })

    const mes = mesDoMovimento(m)
    if (!mes || !janela.has(mes)) continue // fora dos 12 meses → não entra em cards nem gráfico
    if (tipo === "BUY") {
      compras12m.qtd += qtd
      compras12m.valor += m.amount_centavos
      const b = buckets.get(mes)!
      b.qtd += qtd
      b.valor += m.amount_centavos
    } else {
      vendas12m.qtd += qtd
      vendas12m.valor += m.amount_centavos
    }
  }

  return { compras12m, vendas12m, buckets: chaves.map((k) => buckets.get(k)!), negociacoes }
}
