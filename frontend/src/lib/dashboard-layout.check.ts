// Self-check: `npx tsx src/lib/dashboard-layout.check.ts`
import assert from "node:assert/strict"

import {
  CATALOGO,
  layoutPadrao,
  mesclarLayout,
  mesmoLayout,
  mover,
  proximaLargura,
  type WidgetLayout,
} from "./dashboard-layout"

// Sem salvo → padrão, na ordem do catálogo, tudo visível.
assert.deepEqual(mesclarLayout(null), layoutPadrao())
assert.equal(layoutPadrao().length, CATALOGO.length)

// Salvo: ordem preservada; desconhecido e repetido caem; ausente (widget novo) entra no fim.
{
  const salvo = [
    { id: "fluxo", largura: 30, visivel: false },
    { id: "widget-removido", largura: 60, visivel: true },
    { id: "kpi-saldo", largura: 20, visivel: true },
    { id: "fluxo", largura: 60, visivel: true }, // repetido: vale o 1º
  ] as WidgetLayout[]
  const l = mesclarLayout(salvo)
  assert.deepEqual(l.slice(0, 2), [
    { id: "fluxo", largura: 30, visivel: false },
    { id: "kpi-saldo", largura: 20, visivel: true },
  ])
  assert.equal(l.length, CATALOGO.length)
  assert.ok(!l.some((w) => w.id === "widget-removido"))
  const novo = l.find((w) => w.id === "patrimonio")
  assert.deepEqual(novo, { id: "patrimonio", largura: 60, visivel: true })
}

// Largura inválida vinda de fora vira inteira.
assert.equal(
  mesclarLayout([{ id: "fluxo", largura: 6, visivel: true }] as never)[0]
    .largura,
  60
)

// Ciclo de largura e mover com bordas.
assert.equal(proximaLargura(12), 15)
assert.equal(proximaLargura(60), 12)
assert.deepEqual(mover([1, 2, 3], 0, 1), [2, 1, 3])
assert.deepEqual(mover([1, 2, 3], 2, 1), [1, 2, 3])
assert.deepEqual(mover([1, 2, 3], 2, -2), [3, 1, 2])
assert.ok(mesmoLayout(layoutPadrao(), mesclarLayout(null)))

console.log("dashboard-layout: ok")
