/**
 * Self-check puro de `agregarNegociacoes` (sem framework). Rodar de `frontend/`:
 *   npx --yes tsx@4 src/lib/investimento-negociacoes.check.ts
 */
import assert from "node:assert/strict"

import type { InvestimentoTransacao } from "@/lib/api/investimentos"
import { agregarNegociacoes, precoCotaCentavos } from "@/lib/investimento-negociacoes"

const tx = (p: Partial<InvestimentoTransacao> & { id: number }): InvestimentoTransacao =>
  ({ manual: false, amount_centavos: 0, ...p }) as InvestimentoTransacao

const HOJE = "2026-07-15" // mês corrente 2026-07 → janela 2025-08 … 2026-07
const transacoes: InvestimentoTransacao[] = [
  tx({ id: 1, type: "BUY", date: "2026-07-10T12:00:00Z", quantity: "10", value_unitario: "100.00", amount_centavos: 100000 }),
  tx({ id: 2, type: "BUY", date: "2025-08-20T12:00:00Z", quantity: "5", value_unitario: "100.00", amount_centavos: 50000 }),
  tx({ id: 3, type: "BUY", date: "2025-07-05T12:00:00Z", quantity: "3", amount_centavos: 30000 }), // 12+ meses → fora da janela; value_unitario null → fallback
  tx({ id: 4, type: "SELL", date: "2026-07-12T12:00:00Z", quantity: "2", amount_centavos: 25000 }),
  tx({ id: 5, type: "DIVIDEND", date: "2026-07-12T12:00:00Z", amount_centavos: 900 }), // ignorado
  tx({ id: 6, type: "BUY", date: "2026-06-01T12:00:00Z", quantity: "1", amount_centavos: 12000, manual: true }),
]

const r = agregarNegociacoes(transacoes, HOJE)

// Cards (janela de 12 meses-calendário): BUYs #1 + #2 + #6; #3 fica de fora.
assert.deepEqual(r.compras12m, { qtd: 16, valor: 162000 }, "total comprado 12m")
assert.deepEqual(r.vendas12m, { qtd: 2, valor: 25000 }, "total vendido 12m")

// Gráfico: 12 barras fixas, meses vazios = 0, soma = total comprado, mês certo por barra.
assert.equal(r.buckets.length, 12, "12 buckets")
assert.equal(r.buckets[0]!.mes, "2025-08", "primeiro bucket é o mês -11")
assert.equal(r.buckets[11]!.mes, "2026-07", "último bucket é o mês corrente")
assert.equal(
  r.buckets.reduce((s, b) => s + b.valor, 0),
  r.compras12m.valor,
  "soma das barras = total comprado"
)
const jul = r.buckets.find((b) => b.mes === "2026-07")!
assert.deepEqual({ valor: jul.valor, qtd: jul.qtd }, { valor: 100000, qtd: 10 }, "bucket do mês corrente")
const set25 = r.buckets.find((b) => b.mes === "2025-08")!
assert.deepEqual({ valor: set25.valor, qtd: set25.qtd }, { valor: 50000, qtd: 5 }, "bucket -11")

// Tabela: histórico completo de BUY/SELL (inclui o fora-de-janela; exclui o provento).
assert.equal(r.negociacoes.length, 5, "5 negociações (dividendo fora)")
assert.deepEqual(
  r.negociacoes.map((n) => n.id),
  [1, 2, 3, 4, 6],
  "ordem de entrada preservada, sem o provento"
)

// Preço da cota: reais → centavos, com fallback valor/qtd quando value_unitario é null.
assert.equal(precoCotaCentavos(transacoes[0]!), 10000, "preço via value_unitario")
assert.equal(precoCotaCentavos(transacoes[2]!), 10000, "preço via fallback amount/qtd")

console.log("ok — investimento-negociacoes")
