// Self-check: `npx tsx src/lib/categorias-grafico.check.ts`
import assert from "node:assert/strict"

import { distribuirCategorias, ID_OUTRAS } from "./categorias-grafico"

const rotulo = new Map([["a", "Alimentação"]])

// ≤ 8 categorias: todas com slot, sem "Outras"; null vira "Sem categoria"; soma por id.
{
  const d = distribuirCategorias(
    [
      { categoria_id: "a", total_centavos: 100 },
      { categoria_id: null, total_centavos: 300 },
      { categoria_id: "a", total_centavos: 250 },
      { categoria_id: "z", total_centavos: 0 }, // zero some
    ],
    rotulo
  )
  assert.deepEqual(
    d.itens.map((i) => [i.nome, i.valor, i.slot]),
    [
      ["Alimentação", 350],
      ["Sem categoria", 300],
    ].map(([n, v], i) => [n, v, i])
  )
  assert.equal(d.fatias.length, 2)
  assert.equal(d.total, 650)
  assert.equal(d.abatimento, 0)
  assert.equal(d.slotDe(null), 1)
}

// > 8: as 8 maiores levam slot 0..7 em ordem; o resto vira uma fatia "Outras" que fecha o total.
{
  const gastos = Array.from({ length: 11 }, (_, i) => ({
    categoria_id: `c${i}`,
    total_centavos: (i + 1) * 10,
  }))
  const d = distribuirCategorias(gastos, rotulo)
  assert.equal(d.itens.length, 11) // barras-legenda listam todas
  assert.equal(d.itens[0].id, "c10")
  assert.deepEqual(
    d.itens.slice(0, 8).map((i) => i.slot),
    [0, 1, 2, 3, 4, 5, 6, 7]
  )
  assert.equal(d.fatias.length, 9)
  const outras = d.fatias[8]
  assert.equal(outras.id, ID_OUTRAS)
  assert.equal(outras.valor, 10 + 20 + 30)
  assert.equal(
    d.fatias.reduce((s, f) => s + f.valor, 0),
    d.total
  )
  assert.equal(d.slotDe("c0"), null)
  assert.equal(d.slotDe("c10"), 0)
}

console.log("categorias-grafico: ok")

// Categoria com saldo negativo (estorno sem compra no período) não vira fatia: vai para o
// abatimento, e total + abatimento = líquido.
{
  const d = distribuirCategorias(
    [
      { categoria_id: "a", total_centavos: 1000 },
      { categoria_id: "b", total_centavos: -400 },
    ],
    new Map()
  )
  assert.deepEqual(
    d.itens.map((i) => i.id),
    ["a"]
  )
  assert.equal(d.total + d.abatimento, 600)
}
