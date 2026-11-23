// Self-check: `npx tsx src/config/nav.check.ts`
import assert from "node:assert/strict"

import { ATALHOS, ATALHOS_PADRAO, atalhosEfetivos } from "./nav"

const ids = (s: string[] | null) => atalhosEfetivos(s).map((a) => a.id)

assert.deepEqual(ids(null), ATALHOS_PADRAO) // sem escolha → padrão
assert.deepEqual(ids(["chat", "contas", "faturas"]), [
  "chat",
  "contas",
  "faturas",
])
// Desconhecido (saiu do catálogo) e repetido caem; completa com os padrões que faltam.
assert.deepEqual(ids(["sumiu", "chat", "chat"]), [
  "chat",
  "transacoes",
  "orcamentos",
])
// Escolha que já inclui padrões não duplica.
assert.deepEqual(ids(["orcamentos"]), [
  "orcamentos",
  "transacoes",
  "investimentos",
])
assert.equal(new Set(ATALHOS.map((a) => a.id)).size, ATALHOS.length) // ids únicos
// Fronteira do backend: id ^[a-z][a-z-]{0,31}$.
assert.ok(ATALHOS.every((a) => /^[a-z][a-z-]{0,31}$/.test(a.id)))

console.log("nav: ok")
