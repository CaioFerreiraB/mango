/**
 * Self-check puro dos helpers do Tesouro Direto (sem framework). Rodar de `frontend/`:
 *   npx --yes tsx@4 src/lib/tesouro.check.ts
 */
import assert from "node:assert/strict"

import type { Investimento } from "@/lib/api/investimentos"
import {
  liquidoAtual,
  projetarVencimento,
  retornoJanela,
  retornoMensal,
  serieBenchmark,
  tempoRestante,
  type CarteiraSeriePonto,
} from "@/lib/tesouro"

const inv = (p: Partial<Investimento>): Investimento => p as Investimento

// liquidoAtual: prioriza amount_withdrawal; fallback bruto − IR; soma a posição; null sem dado.
assert.equal(
  liquidoAtual([inv({ amount_withdrawal_centavos: 1069180 })]),
  1069180,
  "líquido via amount_withdrawal"
)
assert.equal(
  liquidoAtual([inv({ amount_centavos: 1085742, taxes_centavos: 15000 })]),
  1070742,
  "líquido via fallback bruto − IR"
)
assert.equal(
  liquidoAtual([
    inv({ amount_withdrawal_centavos: 500000 }),
    inv({ amount_centavos: 300000, taxes_centavos: 10000 }),
  ]),
  790000,
  "soma da posição (mistura das duas fontes)"
)
assert.equal(liquidoAtual([]), null, "sem investimentos → null")
assert.equal(liquidoAtual([inv({})]), null, "sem campos de valor → null")

// retornoJanela: pct encadeado + ganho bruto; janela ancora no 1º ponto ≥ início.
const serie: CarteiraSeriePonto[] = [
  { data: "2025-01-02", valor_centavos: 1000000, investido_centavos: 1000000, acumulado_pct: 0 },
  { data: "2025-06-30", valor_centavos: 1040000, investido_centavos: 1000000, acumulado_pct: 4 },
  { data: "2025-12-30", valor_centavos: 1085742, investido_centavos: 1000000, acumulado_pct: 8.5742 },
]
const noAno = retornoJanela(serie, "2025-01-01")!
assert.ok(Math.abs(noAno.pct - 8.5742) < 1e-9, "janela desde o início = acumulado total")
assert.equal(noAno.ganho_centavos, 85742, "ganho R$ = bruto_fim − bruto_ini")
const desdeMeio = retornoJanela(serie, "2025-06-01")!
assert.ok(Math.abs(desdeMeio.pct - ((1.085742 / 1.04 - 1) * 100)) < 1e-9, "janela encadeada")
assert.equal(desdeMeio.ganho_centavos, 45742, "ganho da 2ª metade")
assert.equal(retornoJanela([serie[0]!], "2025-01-01"), null, "menos de 2 pontos → null")

// projetarVencimento IPCA+ : usa o nível ATUAL do IPCA (12m) + cupom real contratado.
const proj = projetarVencimento(
  1085742,
  1020000,
  "2035-05-15",
  { rateType: "IPCA", rate: "6.82", annualRate: null, taxExempt: false },
  0.045, // IPCA 12m atual = 4,5%
  "2026-07-28"
)!
const taxaEsperada = 1.045 * 1.0682 - 1
assert.ok(Math.abs(proj.taxaAnual - taxaEsperada) < 1e-9, "taxa efetiva = (1+ipca)(1+cupom)−1")
assert.ok(Math.abs(proj.anos - 8.8) < 0.1, "anos até o vencimento ~8.8")
assert.equal(
  proj.valorEsperado,
  Math.round(1085742 * Math.pow(1 + taxaEsperada, proj.anos)),
  "valor esperado capitaliza o bruto atual pela taxa efetiva"
)
assert.ok(proj.valorEsperado > 1085742, "cresce até o vencimento")
assert.equal(
  proj.valorLiquidoEsperado,
  proj.valorEsperado - Math.round((proj.valorEsperado - 1020000) * 0.15),
  "líquido esperado desconta 15% do lucro"
)
// SELIC pós-fixado: nível atual da SELIC × (1 + spread).
const selic = projetarVencimento(
  100000,
  100000,
  "2030-01-01",
  { rateType: "SELIC", rate: "0.10", annualRate: null, taxExempt: false },
  0.105, // SELIC 12m atual = 10,5%
  "2026-07-28"
)!
assert.ok(Math.abs(selic.taxaAnual - (1.105 * 1.001 - 1)) < 1e-9, "SELIC atual × spread")
// Prefixado ignora o mercado: usa a taxa travada; isento não desconta IR.
const pre = projetarVencimento(
  100000,
  100000,
  "2030-01-01",
  { rateType: "PREFIXADO", rate: "10", annualRate: "10", taxExempt: true },
  0.5, // nível de mercado é ignorado no prefixado
  "2026-07-28"
)!
assert.ok(Math.abs(pre.taxaAnual - 0.1) < 1e-9, "prefixado usa a taxa travada, não o mercado")
assert.equal(pre.valorLiquidoEsperado, pre.valorEsperado, "isento → líquido = bruto")
assert.equal(
  projetarVencimento(100000, 100000, "2020-01-01", { rateType: "IPCA", rate: "6", annualRate: null, taxExempt: false }, 0.045, "2026-07-28"),
  null,
  "título já vencido → null"
)

// serieBenchmark: mesmos aportes rendendo pelo índice; cada aporte cresce da sua data.
// Aportes: 1000 no dia0 (acc 0), +500 no dia2 (acc 0,10). Índice: 0 / 0,05 / 0,10 / 0,15.
const bench = serieBenchmark([1000, 1000, 1500, 1500], [0, 0.05, 0.1, 0.15])
assert.deepEqual(bench, [
  1000, // 1000 aplicado, sem rendimento ainda
  1050, // 1000 × 1,05
  1600, // 1000 × 1,10 (=1100) + 500 recém-aportado
  1673, // 1000 × 1,15 (=1150) + 500 × (1,15/1,10) (=522,7) → 1672,7
])
assert.deepEqual(serieBenchmark([], []), [], "vazio → vazio")

// tempoRestante
assert.equal(tempoRestante("2035-05-15", "2026-07-28"), "8 anos e 293 dias", "restante formatado")
assert.equal(tempoRestante("2026-07-29", "2026-07-28"), "1 dia", "singular de dia sem anos")
assert.equal(tempoRestante("2020-01-01", "2026-07-28"), null, "já vencido → null")

// retornoMensal: chain-diff do acumulado por mês-calendário completo.
// (a) 3 meses cheios (série começa no dia 1) → ~1,0% cada (1.01^n − 1 encadeado).
const mensal3 = retornoMensal([
  { data: "2025-01-01", acumulado_pct: 0 },
  { data: "2025-01-31", acumulado_pct: 1.0 },
  { data: "2025-02-28", acumulado_pct: 2.01 },
  { data: "2025-03-31", acumulado_pct: 3.0301 },
])
assert.deepEqual(
  mensal3.map((m) => m.mes),
  ["2025-01", "2025-02", "2025-03"],
  "3 meses completos"
)
for (const m of mensal3) assert.ok(Math.abs(m.pct - 1.0) < 1e-9, `mês ${m.mes} ≈ 1,0%`)

// (b) 1º mês parcial descartado; o mês completo seguinte fica EXATO (a base parcial cancela).
const mensalParcial = retornoMensal([
  { data: "2025-01-16", acumulado_pct: 0 },
  { data: "2025-01-31", acumulado_pct: 0.5 }, // janeiro parcial (só 16–31)
  { data: "2025-02-28", acumulado_pct: 1.505 }, // fevereiro cheio → (1.01505/1.005 − 1) = 1,0%
])
assert.equal(mensalParcial.length, 1, "janeiro parcial descartado")
assert.equal(mensalParcial[0]!.mes, "2025-02", "sobra fevereiro")
assert.ok(Math.abs(mensalParcial[0]!.pct - 1.0) < 1e-9, "fevereiro exato apesar da base parcial")

// (c) mês corrente incompleto descartado (série termina no meio do mês).
const mensalCorrente = retornoMensal([
  { data: "2025-01-01", acumulado_pct: 0 },
  { data: "2025-01-31", acumulado_pct: 1.0 },
  { data: "2025-02-15", acumulado_pct: 1.4 }, // fevereiro incompleto
])
assert.deepEqual(
  mensalCorrente.map((m) => m.mes),
  ["2025-01"],
  "só janeiro; fevereiro incompleto fora"
)

// (d) menos de 2 pontos → vazio.
assert.deepEqual(retornoMensal([]), [], "vazio → vazio")
assert.deepEqual(retornoMensal([{ data: "2025-01-01", acumulado_pct: 0 }]), [], "1 ponto → vazio")

console.log("ok — tesouro")
