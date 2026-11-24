// Self-check: npx tsx src/lib/divisao-partes.check.ts
import assert from "node:assert/strict"

import {
  comFatia,
  outrosDaDivisao,
  partesIguais,
  partesValidas,
} from "./divisao-partes"
import type { DivisaoDespesa } from "./api/divisoes"

const p = [{ id: 1 }, { id: 2 }, { id: 3 }]

assert.deepEqual(partesIguais(p, 10_000), { 1: 3334, 2: 3333, 3: 3333 })
assert.ok(partesValidas("porcentagem", 999, 1, p, partesIguais(p, 10_000)))
assert.ok(!partesValidas("porcentagem", 999, 1, p, { 1: 5000, 2: 4000 }))
assert.ok(partesValidas("valor", 10_000, 1, p, { 1: 3000, 2: 7000 }))
assert.ok(!partesValidas("valor", 10_000, 1, p, { 1: 3000, 2: 6000 }))
assert.ok(!partesValidas("valor", 10_000, 1, p, { 1: 10_000 })) // só quem pagou

// Duas pessoas: a outra vira o complemento; três: só a editada muda.
const dois = [{ id: 1 }, { id: 2 }]
assert.deepEqual(comFatia(dois, {}, 1, 1000, 10_000), { 1: 1000, 2: 9000 })
assert.deepEqual(comFatia(dois, { 1: 1000, 2: 9000 }, 2, 500, 10_000), {
  1: 9500,
  2: 500,
})
assert.deepEqual(comFatia(dois, {}, 1, 12_000, 10_000), { 1: 12_000, 2: 0 })
assert.deepEqual(comFatia(p, { 1: 1000 }, 2, 500, 10_000), { 1: 1000, 2: 500 })

const d = {
  pago_por_usuario_id: 1,
  participantes: [
    { usuario_id: 1, valor_centavos: 5000 },
    { usuario_id: 2, valor_centavos: 3000 },
    { usuario_id: 3, valor_centavos: 2000 },
  ],
} as DivisaoDespesa
assert.equal(outrosDaDivisao(d), 5000)

console.log("divisao-partes: ok")
