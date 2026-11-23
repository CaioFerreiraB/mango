/**
 * Self-check sem framework. Rodar de frontend/ (Node 20):
 * node_modules/.bin/tsc --ignoreConfig --module commonjs --target es2022 --esModuleInterop \
 *   --skipLibCheck --types node --outDir /tmp/mango-invest \
 *   src/lib/categoria-investimento.ts src/lib/categoria-investimento.check.ts
 * node /tmp/mango-invest/categoria-investimento.check.js
 */
import assert from "node:assert/strict"

import {
  categoriasDeInvestimento,
  excluidasDoTipo,
} from "./categoria-investimento"

const categorias = [
  { pluggy_id: "03000000", parent_id: null },
  { pluggy_id: "03020000", parent_id: "03000000" },
  { pluggy_id: "03060000", parent_id: "03000000" },
  { pluggy_id: "03060100", parent_id: "03060000" },
  { pluggy_id: "u_tesouro", parent_id: "03020000" }, // personalizada filha
  { pluggy_id: "13000000", parent_id: null },
]

assert.deepEqual([...categoriasDeInvestimento(categorias)].sort(), [
  "03000000",
  "03020000",
  "u_tesouro",
])
// Juros/dividendos (0306) e despesas ficam fora do investimento — e vice-versa.
assert.deepEqual(excluidasDoTipo(categorias, "investimento").sort(), [
  "03060000",
  "03060100",
  "13000000",
])
assert.deepEqual(excluidasDoTipo(categorias, "despesa").sort(), [
  "03000000",
  "03020000",
  "u_tesouro",
])
console.log("categoria-investimento: ok")
