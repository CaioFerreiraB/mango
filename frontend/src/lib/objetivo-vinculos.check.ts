/**
 * Self-check sem framework. Rodar de frontend/ (Node 20):
 * node_modules/.bin/tsc --ignoreConfig --module commonjs --target es2022 --esModuleInterop \
 *   --skipLibCheck --types node --outDir /tmp/mango-vinculos \
 *   src/lib/objetivo-vinculos.ts src/lib/objetivo-vinculos.check.ts
 * node /tmp/mango-vinculos/objetivo-vinculos.check.js
 */
import assert from "node:assert/strict"

import { posicoesDisponiveis } from "./objetivo-vinculos"

const grupos = [
  { chave: "rf-1", nome: "Reserva", code: null, investimento_ids: [1, 2, 3] },
  {
    chave: "rv-TEST11",
    nome: "Fundo",
    code: "TEST11",
    investimento_ids: [4, 5],
  },
  { chave: "rf-2", nome: "Reserva", code: null, investimento_ids: [6] },
  { chave: "rf-avulsa-7", nome: "Reserva", code: null, investimento_ids: [7] },
  { chave: "pos-8", nome: null, code: null, investimento_ids: [8] },
]
const investimentos = new Map([
  [1, { objetivo_id: null }],
  [2, { objetivo_id: 10 }],
  [3, { objetivo_id: null }],
  [4, { objetivo_id: null }],
  [5, { objetivo_id: null }],
  [6, { objetivo_id: null }],
  [7, { objetivo_id: null }],
  // ID 8 ainda não chegou na consulta individual: não presumir que esteja livre.
])

const disponiveis = posicoesDisponiveis(grupos, investimentos)
assert.deepEqual(
  disponiveis.map((p) => p.chave),
  ["rf-1", "rv-TEST11", "rf-2", "rf-avulsa-7"]
)
assert.deepEqual(
  disponiveis.map((p) => p.idsLivres),
  [[1, 3], [4, 5], [6], [7]]
)
assert.deepEqual(disponiveis[0].investimento_ids, [1, 2, 3])
assert.deepEqual(grupos[0].investimento_ids, [1, 2, 3]) // fonte não sofre mutação
assert.deepEqual(posicoesDisponiveis(grupos, new Map()), [])
assert.deepEqual(posicoesDisponiveis([], investimentos), [])

investimentos.set(1, { objetivo_id: 10 })
investimentos.set(3, { objetivo_id: 20 })
assert.equal(
  posicoesDisponiveis(grupos, investimentos).some((p) => p.chave === "rf-1"),
  false
)
console.log("objetivo-vinculos: OK")
