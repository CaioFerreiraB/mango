import type { CarteiraSerie, Investimento } from "@/lib/api/investimentos"
import { hojeISO } from "@/lib/format"

/** Helpers puros do Tesouro Direto (drawer da Carteira). Sem React — testados em `tesouro.check.ts`. */

export type CarteiraSeriePonto = CarteiraSerie["pontos"][number]

function num(v: string | number | null | undefined): number | null {
  if (v == null || v === "") return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

const diaMs = 24 * 3600 * 1000

/** Anos entre duas datas ISO (usa meio-dia UTC p/ não escorregar por fuso). */
function anosEntre(inicioISO: string, fimISO: string): number | null {
  const a = Date.parse(`${inicioISO.slice(0, 10)}T12:00:00Z`)
  const b = Date.parse(`${fimISO.slice(0, 10)}T12:00:00Z`)
  if (!Number.isFinite(a) || !Number.isFinite(b)) return null
  return (b - a) / (365.25 * diaMs)
}

/** Valor líquido atual (líquido de IR) da posição = soma, por investimento, do resgate informado
 *  pelo Pluggy (`amount_withdrawal`), com fallback `bruto − IR` quando ausente. `null` sem dado. */
export function liquidoAtual(invs: Investimento[]): number | null {
  let total = 0
  let temDado = false
  for (const i of invs) {
    if (i.amount_withdrawal_centavos != null) {
      total += i.amount_withdrawal_centavos
      temDado = true
    } else if (i.amount_centavos != null) {
      total += i.amount_centavos - (i.taxes_centavos ?? 0)
      temDado = true
    }
  }
  return temDado ? total : null
}

/** Retorno de uma janela [inicioISO, fim] a partir da série TWR da posição.
 *  `pct` encadeia o acumulado: (1+acc_fim)/(1+acc_ini) − 1. `ganho_centavos ≈ bruto_fim − bruto_ini`.
 *  ponytail: o ganho em R$ é exato só sem aportes/resgates na janela; com fluxos vira aproximação
 *  (a série não separa fluxo de rendimento por dia). */
export function retornoJanela(
  pontos: CarteiraSeriePonto[],
  inicioISO: string
): { pct: number; ganho_centavos: number } | null {
  if (pontos.length < 2) return null
  const ini = pontos.find((p) => p.data >= inicioISO) ?? pontos[0]!
  const fim = pontos[pontos.length - 1]!
  if (ini.data >= fim.data) return null
  const pct = ((1 + fim.acumulado_pct / 100) / (1 + ini.acumulado_pct / 100) - 1) * 100
  return { pct, ganho_centavos: fim.valor_centavos - ini.valor_centavos }
}

/** Último dia civil (`yyyy-mm-dd`) do mês `yyyy-mm`. `Date.UTC(a, m, 0)`: mês 0-indexado, então `m`
 *  (1-indexado) é o mês seguinte e o dia 0 recua p/ o último dia deste mês. */
function ultimoDiaDoMes(mes: string): string {
  const [a, m] = mes.split("-").map(Number)
  return new Date(Date.UTC(a!, m!, 0, 12)).toISOString().slice(0, 10)
}

/** Retorno de cada mês-calendário COMPLETO a partir de uma série diária de `acumulado_pct`
 *  (forward-filled). Chain-diff nas fronteiras de mês: `r_m = (1+acc_fim_m)/(1+acc_fim_{m-1}) − 1`.
 *  Serve tanto p/ a posição (TWR) quanto p/ um indicador (CDI/SELIC/IPCA/IBOV) — ambos expõem
 *  `{ data, acumulado_pct }`. Descarta o 1º mês parcial e o mês corrente incompleto: mantém só meses
 *  cobertos de ponta a ponta pela série. A base do mês parcial inicial cancela na razão, então os
 *  meses completos ficam exatos mesmo quando a janela começa no meio do mês.
 *  ponytail: IPCA (SGS mensal) sai com ~15 dias de defasagem — num mês completo recente ainda não
 *  publicado o acumulado fica plano, então aquele mês lê ≈0% p/ IPCA até o BCB divulgar. */
export function retornoMensal(
  pontos: { data: string; acumulado_pct: number }[]
): { mes: string; pct: number }[] {
  if (pontos.length < 2) return []
  const ordenados = [...pontos].sort((a, b) => a.data.localeCompare(b.data))
  // mês (yyyy-mm) → acc do último ponto do mês; ordem de inserção = ordem de calendário (série contínua).
  const fimDoMes = new Map<string, number>()
  for (const pt of ordenados) fimDoMes.set(pt.data.slice(0, 7), pt.acumulado_pct)

  const primeiro = ordenados[0]!.data
  const ultimo = ordenados[ordenados.length - 1]!.data
  const out: { mes: string; pct: number }[] = []
  let base = 0
  for (const [mes, acc] of fimDoMes) {
    const pct = ((1 + acc / 100) / (1 + base / 100) - 1) * 100
    base = acc // encadeia sempre, mesmo nos meses descartados, p/ a base ficar correta
    if (`${mes}-01` >= primeiro && ultimoDiaDoMes(mes) <= ultimo) out.push({ mes, pct })
  }
  return out
}

export interface DadosProjecao {
  rateType: string | null | undefined
  rate: string | number | null | undefined
  annualRate: string | number | null | undefined
  taxExempt: boolean | null | undefined
}

/** Código do indicador (BCB) que rege o título, p/ buscar o nível anual atual do indexador.
 *  Prefixado/desconhecido → null (a taxa foi travada na contratação, não depende do mercado). */
export function indicadorDoTitulo(rateType: string | null | undefined): string | null {
  const t = (rateType ?? "").trim().toUpperCase()
  if (t === "IPCA" || t === "IGPM" || t === "IGP-M") return "ipca"
  if (t === "SELIC") return "selic"
  if (t === "CDI" || t === "DI") return "cdi"
  return null
}

/** Taxa anual efetiva (fração, ex.: 0.11). Pós-fixados/indexados usam o **nível atual** do indexador
 *  (`nivelIndexadorAnual`, fração dos últimos 12m) composto com o spread contratado (`rate`);
 *  prefixado usa a taxa travada (`annualRate` senão `rate`). */
function taxaAnualEfetiva(d: DadosProjecao, nivelIndexadorAnual: number | null): number | null {
  const tipo = (d.rateType ?? "").trim().toUpperCase()
  const rate = num(d.rate)
  const annual = num(d.annualRate)
  if (tipo === "IPCA" || tipo === "IGPM" || tipo === "IGP-M") {
    // IPCA+: (1 + inflação atual) × (1 + cupom real) − 1.
    if (nivelIndexadorAnual != null && rate != null)
      return (1 + nivelIndexadorAnual) * (1 + rate / 100) - 1
    return annual != null ? annual / 100 : rate != null ? rate / 100 : null
  }
  if (tipo === "SELIC") {
    // Tesouro Selic: SELIC atual × (1 + spread), spread costuma ser pequeno.
    if (nivelIndexadorAnual != null) return (1 + nivelIndexadorAnual) * (1 + (rate ?? 0) / 100) - 1
    return annual != null ? annual / 100 : null
  }
  if (tipo === "CDI" || tipo === "DI") {
    // % do CDI (raro em Tesouro): CDI atual × (rate% ou 100%).
    if (nivelIndexadorAnual != null) return nivelIndexadorAnual * (rate != null ? rate / 100 : 1)
    return annual != null ? annual / 100 : null
  }
  // Prefixado / desconhecido: taxa anual travada na contratação.
  if (annual != null) return annual / 100
  return rate != null ? rate / 100 : null
}

/** Projeção (estimativa) do valor no vencimento sem novos aportes/resgates: capitaliza o valor
 *  **bruto atual** por juros compostos à taxa anual efetiva até `dueDate`. Pós-fixados/indexados
 *  usam o nível atual do indexador (`nivelIndexadorAnual`, fração 12m); prefixado, a taxa travada.
 *  ponytail: estimativa — assume o nível atual do indexador constante até o vencimento e ignora
 *  marcação a mercado; IR do lucro projetado a 15% (faixa +720d), isento se `taxExempt`.
 *  `null` quando faltam dados ou o título já venceu. */
export function projetarVencimento(
  brutoCentavos: number,
  aplicadoCentavos: number,
  dueDate: string,
  dados: DadosProjecao,
  nivelIndexadorAnual: number | null,
  hoje = hojeISO()
): { valorEsperado: number; valorLiquidoEsperado: number; anos: number; taxaAnual: number } | null {
  const anos = anosEntre(hoje, dueDate)
  if (anos == null || anos <= 0 || brutoCentavos <= 0) return null
  const taxa = taxaAnualEfetiva(dados, nivelIndexadorAnual)
  if (taxa == null) return null
  const valorEsperado = Math.round(brutoCentavos * Math.pow(1 + taxa, anos))
  const lucro = Math.max(0, valorEsperado - aplicadoCentavos)
  const ir = dados.taxExempt ? 0 : Math.round(lucro * 0.15)
  return { valorEsperado, valorLiquidoEsperado: valorEsperado - ir, anos, taxaAnual: taxa }
}

/** Valor de um benchmark (CDI/SELIC/IPCA/IBOV) que recebe os **mesmos aportes** da posição: cada
 *  aporte (Δ do aplicado acumulado no dia) rende pelo índice a partir da sua data. Entradas alinhadas
 *  por dia — `aplicadoAcum` (centavos, acumulado) e `accIndice` (fração acumulada do índice desde o
 *  início da janela). `B(d) = (1+acc[d])·Σ_{a≤d} Δaplicado(a)/(1+acc[a])`. */
export function serieBenchmark(aplicadoAcum: number[], accIndice: number[]): number[] {
  const out: number[] = []
  let soma = 0
  let anterior = 0
  for (let i = 0; i < aplicadoAcum.length; i++) {
    const acc = accIndice[i] ?? 0
    soma += (aplicadoAcum[i]! - anterior) / (1 + acc)
    anterior = aplicadoAcum[i]!
    out.push(Math.round((1 + acc) * soma))
  }
  return out
}

/** "9 anos e 298 dias" restantes até o vencimento; `null` se já venceu ou a data é inválida.
 *  ponytail: ano = 365 dias na quebra (exibição), não conta bissextos. */
export function tempoRestante(dueDate: string, hoje = hojeISO()): string | null {
  const a = Date.parse(`${hoje.slice(0, 10)}T12:00:00Z`)
  const b = Date.parse(`${dueDate.slice(0, 10)}T12:00:00Z`)
  if (!Number.isFinite(a) || !Number.isFinite(b) || b <= a) return null
  let dias = Math.round((b - a) / diaMs)
  const anos = Math.floor(dias / 365)
  dias -= anos * 365
  const partes: string[] = []
  if (anos > 0) partes.push(`${anos} ${anos === 1 ? "ano" : "anos"}`)
  partes.push(`${dias} ${dias === 1 ? "dia" : "dias"}`)
  return partes.join(" e ")
}
