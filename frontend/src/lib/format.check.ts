/**
 * Self-check dos formatadores de data (sem framework). Rodar de `frontend/`:
 *   npx --yes tsx@4 src/lib/format.check.ts
 */
import assert from "node:assert/strict"

import {
  diaCivilSP,
  formatDataCurta,
  formatDate,
  formatMesAno,
  mesISO,
} from "@/lib/format"

// Data civil pura (`yyyy-mm-dd`) não pode "voltar" um dia pelo fuso SP — o rótulo do orçamento
// mostrava "outubro" para 2026-11-01.
assert.match(formatMesAno("2026-11-01"), /novembro de 2026/)
assert.equal(mesISO("2026-11-01"), "2026-11")
assert.equal(diaCivilSP("2026-03-01"), "2026-03-01")
assert.match(formatDate("2026-11-01"), /^1 de nov/)

// Data-hora ISO continua sendo convertida para o fuso SP (01h UTC = 22h do dia anterior em SP).
assert.equal(diaCivilSP("2026-11-01T01:00:00Z"), "2026-10-31")
assert.equal(mesISO("2026-11-01T01:00:00Z"), "2026-10")

// Data curta de tabela: sem ano no ano corrente, com ano fora dele; dia civil no fuso SP.
assert.equal(formatDataCurta("2026-11-23", "2026-11-25"), "23 nov")
assert.equal(formatDataCurta("2025-12-05", "2026-11-25"), "5 dez 2025")
assert.equal(
  formatDataCurta("2026-01-01T01:00:00Z", "2026-11-25"),
  "31 dez 2025"
)

console.log("format.check: ok")
