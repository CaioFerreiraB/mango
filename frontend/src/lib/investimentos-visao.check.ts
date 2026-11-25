// Self-check: `npx tsx src/lib/investimentos-visao.check.ts`
import assert from "node:assert/strict"

import {
  aPartirDaPrimeiraPosicao,
  fechamentosMensais,
  matrizRentabilidade,
  vencimentosPorMes,
} from "./investimentos-visao"

// Fecho mensal: último ponto do mês, fora de ordem na entrada; custo desconhecido vira null.
assert.deepEqual(
  fechamentosMensais([
    { data: "2026-02-28", valor_centavos: 300, investido_centavos: 250 },
    { data: "2026-01-10", valor_centavos: 100, investido_centavos: 100 },
    { data: "2026-01-31", valor_centavos: 110, investido_centavos: 100 },
    { data: "2026-03-31", valor_centavos: 400, investido_centavos: 0 },
  ]),
  [
    { mes: "2026-01", valor: 110, investido: 100 },
    { mes: "2026-02", valor: 300, investido: 250 },
    { mes: "2026-03", valor: 400, investido: null },
  ]
)

// Matriz: anos do mais recente; ano composto; CDI só nos meses da carteira.
{
  const m = matrizRentabilidade(
    [
      { mes: "2025-12", pct: 1 },
      { mes: "2026-01", pct: 10 },
      { mes: "2026-02", pct: -5 },
    ],
    [
      { mes: "2025-11", pct: 50 }, // sem carteira no mês: fora do total do CDI
      { mes: "2025-12", pct: 0.9 },
      { mes: "2026-01", pct: 1 },
    ]
  )
  assert.deepEqual(
    m.map((l) => l.ano),
    [2026, 2025]
  )
  assert.equal(m[0].meses[0], 10)
  assert.equal(m[0].meses[1], -5)
  assert.equal(m[0].meses[2], null)
  assert.ok(Math.abs(m[0].total! - 4.5) < 1e-9) // 1.10 × 0.95 − 1
  assert.equal(m[0].cdi[1], null) // CDI de fev ausente
  assert.equal(m[0].totalCdi, null) // → sem CDI do ano (seria 1 mês contra 2)
  assert.ok(Math.abs(m[1].totalCdi! - 0.9) < 1e-9) // nov/25 (50%) ignorado
}

// Vencimentos: só de hoje em diante, agrupados e ordenados.
{
  const v = vencimentosPorMes(
    [
      {
        id: 1,
        nome: "CDB A",
        valor_centavos: 100,
        due_date: "2027-03-20T00:00:00Z",
      },
      {
        id: 2,
        nome: "Vencido",
        valor_centavos: 999,
        due_date: "2026-01-01T00:00:00Z",
      },
      {
        id: 3,
        nome: "LCI",
        valor_centavos: 50,
        due_date: "2026-12-05T00:00:00Z",
      },
      {
        id: 4,
        nome: "CDB B",
        valor_centavos: 30,
        due_date: "2027-03-02T00:00:00Z",
      },
      { id: 5, nome: "Sem data", valor_centavos: 10, due_date: null },
      {
        id: 6,
        nome: "Hoje",
        valor_centavos: 5,
        due_date: "2026-11-25T00:00:00Z",
      },
    ],
    "2026-11-25"
  )
  assert.deepEqual(
    v.map((g) => [g.mes, g.total, g.itens.map((i) => i.id)]),
    [
      ["2026-11", 5, [6]],
      ["2026-12", 50, [3]],
      ["2027-03", 130, [4, 1]],
    ]
  )
}

// Sem posição no começo → corta; zero no meio (resgate total) fica.
assert.deepEqual(
  aPartirDaPrimeiraPosicao([
    { data: "a", valor_centavos: 0 },
    { data: "b", valor_centavos: 5 },
    { data: "c", valor_centavos: 0 },
  ]).map((p) => p.data),
  ["b", "c"]
)
assert.deepEqual(aPartirDaPrimeiraPosicao([{ valor_centavos: 0 }]), [])

console.log("investimentos-visao: ok")
