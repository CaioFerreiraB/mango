/**
 * Self-check do nome de exibição de ativo (sem framework). Rodar de `frontend/`:
 *   npx --yes tsx@4 src/lib/investimento-taxonomia.check.ts
 */
import assert from "node:assert/strict"

import { nomeAtivo } from "@/lib/investimento-taxonomia"

// Caixinha do Nubank como vem do Pluggy (nome real).
assert.equal(
  nomeAtivo(
    "CDB - NU FINANCEIRA S.A. - SOCIEDADE DE CREDITO, FINANCIAMENTO E INVESTIMENTO"
  ),
  "CDB · Nu Financeira"
)
assert.equal(nomeAtivo("CDB - BANCO INTER S/A"), "CDB · Banco Inter")
assert.equal(nomeAtivo("LCI - BANCO XP SA"), "LCI · Banco Xp")
assert.equal(
  nomeAtivo("CDB - MERCADO CREDITO SOCIEDADE DE CREDITO, FINANCIAMENTO"),
  "CDB · Mercado Credito Sociedade De Credito"
)
// Nome do usuário / outros papéis passam intactos.
assert.equal(nomeAtivo("Caixinha Viagem"), "Caixinha Viagem")
assert.equal(nomeAtivo("Tesouro Selic 2028"), "Tesouro Selic 2028")
assert.equal(nomeAtivo("CDB"), "CDB")
assert.equal(nomeAtivo(null), null)

console.log("investimento-taxonomia.check: ok")
