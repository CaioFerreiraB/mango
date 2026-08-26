/**
 * Self-check puro de `agregarProventos` (sem framework). Rodar de `frontend/`:
 *   npx --yes tsx@4 src/lib/investimento-proventos.check.ts
 */
import assert from "node:assert/strict"

import type { InvestimentoTransacao } from "@/lib/api/investimentos"
import { agregarProventos } from "@/lib/investimento-proventos"

const tx = (
  p: Partial<InvestimentoTransacao> & { id: number }
): InvestimentoTransacao =>
  ({ manual: false, amount_centavos: 0, ...p }) as InvestimentoTransacao

const HOJE = "2026-07-15" // mês corrente 2026-07 → janela 2025-08 … 2026-07

// API já vem por dia DESC. Espelha o caso real: rendimentos sem value_unitario/quantity.
const proventos: InvestimentoTransacao[] = [
  tx({
    id: 1,
    type: "INTEREST",
    date: "2026-07-14T12:00:00Z",
    amount_centavos: 1748,
  }), // real: só total
  tx({
    id: 2,
    type: "INTEREST",
    date: "2026-06-13T12:00:00Z",
    amount_centavos: 1748,
  }),
  tx({
    id: 3,
    type: "DIVIDEND",
    date: "2025-05-14T12:00:00Z",
    value_unitario: "0.088",
    quantity: "1000",
    amount_centavos: 8800,
  }), // sandbox: com value/qtd, mas 14 meses atrás → fora do gráfico
]

const r = agregarProventos(proventos, HOJE)

// Total all-time = soma de todos os amount_centavos (inclui o fora-de-janela).
assert.equal(r.totalCentavos, 12296, "total all-time")

// Último provento (mais recente, id 1): sem value/qtd → por-cota null; total e data presentes.
assert.equal(
  r.ultimoPorCotaReais,
  null,
  "último por cota null quando a API não manda value/qtd"
)
assert.equal(r.ultimoTotalCentavos, 1748, "último total (fallback do card)")
assert.equal(r.ultimoQuando, "2026-07-14T12:00:00Z", "data do último provento")

// Gráfico: 12 barras fixas; só os proventos dentro da janela somam.
assert.equal(r.buckets.length, 12, "12 buckets")
assert.equal(r.buckets[0]!.mes, "2025-08", "primeiro bucket é o mês -11")
assert.equal(r.buckets[11]!.mes, "2026-07", "último bucket é o mês corrente")
assert.equal(
  r.buckets.reduce((s, b) => s + b.totalCentavos, 0),
  3496,
  "soma das barras = proventos na janela"
)
assert.equal(
  r.buckets.find((b) => b.mes === "2026-07")!.totalCentavos,
  1748,
  "bucket do mês corrente"
)
assert.equal(
  r.buckets.find((b) => b.mes === "2025-05")!,
  undefined,
  "mês -14 não está na janela"
)

// Tabela: todos os proventos (só mês + total), ordem preservada.
assert.deepEqual(
  r.linhas.map((l) => l.id),
  [1, 2, 3],
  "todas as linhas, ordem preservada"
)
assert.equal(r.linhas[0]!.totalCentavos, 1748, "total da linha")
assert.notEqual(
  r.linhas[0]!.label,
  "—",
  "label do mês preenchido quando há data"
)

// Quando a API manda value_unitario, o por-cota do último provento é preciso (sub-centavo).
const comValor = agregarProventos([proventos[2]!], HOJE)
assert.ok(
  Math.abs(comValor.ultimoPorCotaReais! - 0.088) < 1e-9,
  "por-cota preserva precisão sub-centavo"
)

console.log("ok — investimento-proventos")
