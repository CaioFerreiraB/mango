/**
 * Agregação dos proventos (rendimentos) de uma posição de FII — consumido pela aba Dividendos do
 * drawer. Puro (sem React), para ser testável: veja `investimento-proventos.check.ts`.
 *
 * Cards e tabela cobrem o histórico completo (all-time); o gráfico usa a mesma janela de **12
 * meses-calendário** da aba Movimentações (`ultimosMeses`). A API real do Pluggy manda os rendimentos
 * (INTEREST) só com o **total** — sem valor por cota nem cotas — então a tabela lista mês + total, e o
 * card de "último rendimento por cota" cai para `total ÷ cotas atuais` quando não há `value_unitario`.
 */
import type { InvestimentoTransacao } from "@/lib/api/investimentos"
import { formatBucketLabel, mesISO } from "@/lib/format"
import { ultimosMeses } from "@/lib/investimento-negociacoes"

/** Uma barra do gráfico de rendimentos (um mês-calendário). `totalCentavos` = soma recebida no mês. */
export type BucketProvento = { mes: string; label: string; totalCentavos: number }

/** Linha da tabela de proventos: só mês + total (o Pluggy não manda por-cota/cotas em dados reais). */
export type LinhaProvento = {
  id: number
  mes: string // yyyy-mm
  label: string // ex.: jul/25
  quando: string | null // data original (ISO) p/ formatDate; null quando sem data
  totalCentavos: number // amount_centavos (sempre presente)
}

export type AgregadoProventos = {
  totalCentavos: number // soma de TODOS os proventos (all-time)
  ultimoPorCotaReais: number | null // rend. por cota do último provento, quando a API manda value/qtd
  ultimoTotalCentavos: number | null // total do último provento (fallback do card quando por-cota é null)
  ultimoQuando: string | null // data do último provento (p/ "cota em …")
  buckets: BucketProvento[] // 12 meses fixos, ordem crescente
  linhas: LinhaProvento[] // todos os proventos, ordem de entrada preservada (API já vem DESC)
}

const num = (v: string | null | undefined) => (v == null ? 0 : Number(v))

/** Rendimento por cota em reais: `value_unitario` (reais) ou, na falta, valor total ÷ cotas. `null`
 *  quando a API não manda nenhum dos dois (caso comum dos rendimentos reais do Pluggy). */
function porCotaReaisDe(m: InvestimentoTransacao): number | null {
  if (m.value_unitario != null) return Number(m.value_unitario)
  const q = num(m.quantity)
  return q > 0 ? m.amount_centavos / 100 / q : null
}

/** Mês SP (`yyyy-mm`) de um provento, a partir do timestamp original (não do dia fatiado, que viraria
 *  meia-noite UTC e escorregaria de mês no fuso SP). `null` quando sem data. */
function mesDoProvento(m: InvestimentoTransacao): string | null {
  const quando = m.date ?? m.trade_date
  return quando ? mesISO(quando) : null
}

/**
 * @param hoje data SP corrente `yyyy-mm-dd` (de `hojeISO()`) — injetada p/ ficar determinístico.
 */
export function agregarProventos(
  proventos: InvestimentoTransacao[],
  hoje: string
): AgregadoProventos {
  const chaves = ultimosMeses(hoje.slice(0, 7), 12)
  const buckets = new Map<string, BucketProvento>(
    chaves.map((k) => [k, { mes: k, label: formatBucketLabel(`${k}-01`, "mensal"), totalCentavos: 0 }])
  )
  const janela = new Set(chaves)

  let totalCentavos = 0
  const linhas: LinhaProvento[] = []

  for (const m of proventos) {
    const mes = mesDoProvento(m)
    totalCentavos += m.amount_centavos
    linhas.push({
      id: m.id,
      mes: mes ?? "",
      label: mes ? formatBucketLabel(`${mes}-01`, "mensal") : "—",
      quando: m.date ?? m.trade_date ?? null,
      totalCentavos: m.amount_centavos,
    })
    if (mes && janela.has(mes)) buckets.get(mes)!.totalCentavos += m.amount_centavos
  }

  // Mais recente: API já vem por dia DESC, então é o 1º provento com data.
  const ultimo = proventos.find((m) => (m.date ?? m.trade_date) != null) ?? null
  return {
    totalCentavos,
    ultimoPorCotaReais: ultimo ? porCotaReaisDe(ultimo) : null,
    ultimoTotalCentavos: ultimo?.amount_centavos ?? null,
    ultimoQuando: ultimo ? (ultimo.date ?? ultimo.trade_date ?? null) : null,
    buckets: chaves.map((k) => buckets.get(k)!),
    linhas,
  }
}
