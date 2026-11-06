/**
 * Self-check dos formatadores de data (sem framework). Rodar de `frontend/`:
 *   npx --yes tsx@4 src/lib/format.check.ts
 */
import assert from "node:assert/strict"

import { diaCivilSP, formatDate, formatMesAno, mesISO } from "@/lib/format"

// Data civil pura (`yyyy-mm-dd`) não pode "voltar" um dia pelo fuso SP — o rótulo do orçamento
// mostrava "outubro" para 2026-11-01.
assert.match(formatMesAno("2026-11-01"), /novembro de 2026/)
assert.equal(mesISO("2026-11-01"), "2026-11")
assert.equal(diaCivilSP("2026-03-01"), "2026-03-01")
assert.match(formatDate("2026-11-01"), /^1 de nov/)

// Data-hora ISO continua sendo convertida para o fuso SP (01h UTC = 22h do dia anterior em SP).
assert.equal(diaCivilSP("2026-11-01T01:00:00Z"), "2026-10-31")
assert.equal(mesISO("2026-11-01T01:00:00Z"), "2026-10")

console.log("format.check: ok")
