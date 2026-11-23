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

// Salvo: ordem preservada; desconhecido e repetido caem; ausente (widget novo) entra logo depois
// do vizinho anterior no catálogo (ou no início, sem nenhum anterior no salvo).
{
  const salvo = [
    { id: "fluxo", largura: 30, visivel: false },
    { id: "widget-removido", largura: 60, visivel: true },
    { id: "categorias", largura: 60, visivel: true }, // foi para a aba Despesas
    { id: "kpi-saldo", largura: 20, visivel: true },
    { id: "fluxo", largura: 60, visivel: true }, // repetido: vale o 1º
  ] as WidgetLayout[]
  const l = mesclarLayout(salvo)
  assert.deepEqual(
    l.map((w) => w.id),
    [
      "fluxo",
      "patrimonio", // depois de fluxo
      "kpi-saldo",
      "kpi-entradas", // depois de kpi-saldo
      "kpi-saidas",
      "kpi-resultado",
      "kpi-investido",
      "ultimas",
    ]
  )
  assert.deepEqual(l[0], { id: "fluxo", largura: 30, visivel: false })
  assert.deepEqual(l[2], { id: "kpi-saldo", largura: 20, visivel: true })
  assert.equal(l.length, CATALOGO.length)
  assert.ok(!l.some((w) => w.id === "widget-removido" || w.id === "categorias"))
  const novo = l.find((w) => w.id === "patrimonio")
  assert.deepEqual(novo, { id: "patrimonio", largura: 60, visivel: true })
}

// Layout salvo antes de "ultimas" existir: o widget novo nasce logo abaixo dos cards.
{
  const antigo = layoutPadrao().filter((w) => w.id !== "ultimas")
  const ids = mesclarLayout(antigo).map((w) => w.id)
  assert.equal(ids.indexOf("ultimas"), ids.indexOf("kpi-investido") + 1)
}

// Sem nenhum vizinho anterior no salvo → início.
assert.equal(
  mesclarLayout([{ id: "patrimonio", largura: 60, visivel: true }])[0].id,
  "kpi-saldo"
)

// Largura inválida vinda de fora vira inteira.
assert.equal(
  mesclarLayout([{ id: "fluxo", largura: 6, visivel: true }] as never).find(
    (w) => w.id === "fluxo"
  )?.largura,
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
