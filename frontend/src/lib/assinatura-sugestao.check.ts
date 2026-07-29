/**
 * Self-check da heurística de sugestão (§4.7). Sem framework de teste no projeto — asserts + node.
 * Fica fora do `tsc -b` (excluído em tsconfig.app.json) por depender de `node:`. Rodar de frontend/
 * (Node 20):
 *   node_modules/.bin/tsc --ignoreConfig --module commonjs --target es2022 --esModuleInterop \
 *     --skipLibCheck --outDir /tmp/sug src/lib/assinatura-sugestao.ts src/lib/assinatura-sugestao.check.ts \
 *   && node /tmp/sug/assinatura-sugestao.check.js
 */

import assert from "node:assert/strict"

import { normalizar, ratioLevenshtein, sugerir } from "./assinatura-sugestao"

const netflix = { id: 1, nome: "Netflix", nomes_transacao: ["NETFLIX*BR"] }
const spotify = { id: 2, nome: "Spotify", nomes_transacao: [] }
const lista = [netflix, spotify]

// normalização remove acento/caixa/espaço extra.
assert.equal(normalizar("  Áçãí  BR "), "acai br")

// razão: iguais = 1, disjuntos baixos.
assert.equal(ratioLevenshtein("netflix", "netflix"), 1)
assert.ok(ratioLevenshtein("netflix", "spotify") < 0.5)

// contém (prefixo de banco) → casa Netflix.
assert.deepEqual(sugerir("PAG*Netflix", lista), { id: 1, nome: "Netflix" })
// sufixo de banco → casa pelo alias/contido.
assert.deepEqual(sugerir("NETFLIX.COM AMSTERDAM", lista), {
  id: 1,
  nome: "Netflix",
})
// erro de digitação → casa por razão de edição.
assert.deepEqual(sugerir("Netfliix", lista), { id: 1, nome: "Netflix" })
// nada a ver → sem sugestão.
assert.equal(sugerir("Uber Trip", lista), null)
// texto muito curto → sem sugestão.
assert.equal(sugerir("ab", lista), null)

console.log("assinatura-sugestao: OK")
