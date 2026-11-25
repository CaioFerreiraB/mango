// Self-check: `npx tsx src/lib/calendario-calor.check.ts`
import assert from "node:assert/strict"

import {
  contraste,
  corTexto,
  intensidade,
  misturar,
  semanasDoMes,
} from "./calendario-calor"

// Mistura nas pontas e no meio.
assert.equal(
  misturar("rgba(255,255,255,1)", "rgb(0,0,0)", 0),
  "rgb(255,255,255)"
)
assert.equal(misturar("rgba(255,255,255,1)", "rgb(0,0,0)", 1), "rgb(0,0,0)")
assert.equal(misturar("rgb(0,0,0)", "rgb(200,100,50)", 0.5), "rgb(100,50,25)")

// Contraste WCAG: preto × branco = 21.
assert.equal(Math.round(contraste("rgb(0,0,0)", "rgb(255,255,255)")), 21)

// Em qualquer fundo da escala (claro e escuro, laranja e azul, todo peso) o texto escolhido tem AA.
const temas = [
  {
    card: "rgb(255,255,255)",
    ink: "rgb(49,56,66)",
    pos: "rgb(66,104,241)",
    neg: "rgb(243,104,70)",
  },
  {
    card: "rgb(25,30,32)",
    ink: "rgb(230,233,238)",
    pos: "rgb(66,104,241)",
    neg: "rgb(243,104,70)",
  },
]
for (const t of temas)
  for (const alvo of [t.pos, t.neg])
    for (let w = 0; w <= 1.0001; w += 0.02) {
      const fundo = misturar(t.card, alvo, w)
      const txt = corTexto(fundo, [
        t.ink,
        t.card,
        "rgb(0,0,0)",
        "rgb(255,255,255)",
      ])
      assert.ok(
        contraste(txt, fundo) >= 4.5,
        `${fundo} w=${w.toFixed(2)} → ${txt}`
      )
    }

// Intensidade: zero é neutro, cada lado normaliza pelo próprio extremo, piso 0.12, teto 1.
assert.equal(intensidade(0, 100, 100), 0)
assert.equal(intensidade(100, 100, 10), 1)
assert.equal(intensidade(-10, 100, 10), -1)
assert.ok(Math.abs(intensidade(1, 1000, 1) - 0.12088) < 1e-4)
assert.equal(intensidade(-5, 0, 0), -1) // sem referência (não deveria ocorrer) → extremo

// Semanas: nov/2026 começa num domingo (sem casas vazias antes); fev/2026 tem 28 dias.
const nov = semanasDoMes(2026, 11)
assert.equal(nov[0][0], "2026-11-01")
assert.equal(nov.flat().filter(Boolean).length, 30)
assert.ok(nov.every((s) => s.length === 7))
const fev = semanasDoMes(2026, 2)
assert.equal(fev[0][0], "2026-02-01") // 01/02/2026 é domingo
assert.equal(fev.flat().filter(Boolean).at(-1), "2026-02-28")
const mar = semanasDoMes(2026, 3)
assert.equal(mar[0].indexOf("2026-03-01"), 0)
const out = semanasDoMes(2026, 10) // 01/10/2026 é quinta → 4 casas vazias
assert.deepEqual(out[0].slice(0, 4), [null, null, null, null])
assert.equal(out[0][4], "2026-10-01")

console.log("calendario-calor: ok")
