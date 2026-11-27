// Self-check: `npx tsx src/lib/dashboard-layout.check.ts`
import assert from "node:assert/strict"

import {
  CATALOGO,
  layoutPadrao,
  mesclarLayout,
  mesmoLayout,
  abaDe,
  encaixarAltura,
  encaixarLargura,
  mover,
  passoLargura,
  restaurarAba,
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
      "calendario", // depois de fluxo
      "patrimonio", // depois de calendario
      // abas Receitas e Despesas (novas): depois do último da Geral no catálogo
      ...CATALOGO.filter((w) => abaDe(w.id) !== "geral").map((w) => w.id),
      "kpi-saldo",
      "kpi-entradas", // depois de kpi-saldo
      "kpi-saidas",
      "kpi-resultado",
      "kpi-investido",
      "despesas-fixas", // novo: depois de kpi-investido
      "despesas-fixas-proximos",
      "ultimas",
    ]
  )
  assert.deepEqual(l[0], { id: "fluxo", largura: 30, visivel: false })
  assert.deepEqual(
    l.find((w) => w.id === "kpi-saldo"),
    {
      id: "kpi-saldo",
      largura: 20,
      visivel: true,
    }
  )
  assert.equal(l.length, CATALOGO.length)
  assert.ok(!l.some((w) => w.id === "widget-removido" || w.id === "categorias"))
  const novo = l.find((w) => w.id === "patrimonio")
  assert.deepEqual(novo, { id: "patrimonio", largura: 60, visivel: true })
}

// Layout salvo antes de "despesas-fixas"/"ultimas" existirem: os novos nascem logo abaixo dos
// cards, na ordem do catálogo.
{
  const antigo = layoutPadrao().filter(
    (w) => w.id !== "ultimas" && !w.id.startsWith("despesas-fixas")
  )
  const ids = mesclarLayout(antigo).map((w) => w.id)
  assert.equal(ids.indexOf("despesas-fixas"), ids.indexOf("kpi-investido") + 1)
  assert.equal(
    ids.indexOf("despesas-fixas-proximos"),
    ids.indexOf("despesas-fixas") + 1
  )
  assert.equal(
    ids.indexOf("ultimas"),
    ids.indexOf("despesas-fixas-proximos") + 1
  )
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

// Borda arrastada encaixa na fração mais próxima; teclado anda entre elas, parando nas bordas.
assert.equal(encaixarLargura(31), 30)
assert.equal(encaixarLargura(13), 12)
assert.equal(encaixarLargura(2), 10)
assert.equal(encaixarLargura(80), 60)
assert.equal(passoLargura(15, 1), 20)
assert.equal(passoLargura(60, 1), 60)
assert.equal(passoLargura(10, -1), 10)
assert.equal(encaixarAltura(301), 304)
assert.equal(encaixarAltura(10), 96)

// Altura: válida fica; fora dos limites some. Largura fora das frações vira a padrão do widget.
{
  const l = mesclarLayout([
    { id: "fluxo", largura: 30, altura: 400, visivel: true },
    { id: "calendario", largura: 30, altura: 5, visivel: true },
    { id: "kpi-saidas", largura: 7, visivel: true },
  ])
  assert.deepEqual(
    l.find((w) => w.id === "fluxo"),
    {
      id: "fluxo",
      largura: 30,
      altura: 400,
      visivel: true,
    }
  )
  assert.equal(l.find((w) => w.id === "calendario")?.altura, undefined)
  assert.equal(l.find((w) => w.id === "kpi-saidas")?.largura, 15)
}

// Restaurar uma aba não mexe nas outras; a ordem entre abas não conta como mudança.
{
  const mexido = layoutPadrao().map((w) =>
    w.id === "fluxo" || w.id === "rec-fontes" ? { ...w, largura: 20 } : w
  )
  const r = restaurarAba(mexido, "receitas")
  assert.equal(r.find((w) => w.id === "rec-fontes")?.largura, 30)
  assert.equal(r.find((w) => w.id === "fluxo")?.largura, 20)
  assert.ok(mesmoLayout(restaurarAba(layoutPadrao(), "geral"), layoutPadrao()))
}

// Mínimo por widget: o saldo não desce de ⅓ (nem arrastando, nem pelo teclado, nem salvo).
assert.equal(encaixarLargura(10, "kpi-saldo"), 20)
assert.equal(passoLargura(20, -1, "kpi-saldo"), 20)
assert.equal(
  mesclarLayout([{ id: "kpi-saldo", largura: 10, visivel: true }]).find(
    (w) => w.id === "kpi-saldo"
  )?.largura,
  60
)

// Mesma configuração com chaves em outra ordem não conta como mudança.
assert.ok(
  mesmoLayout(
    [{ id: "fluxo", largura: 30, altura: 400, visivel: true }],
    [{ visivel: true, altura: 400, id: "fluxo", largura: 30 }]
  )
)

// Mover com bordas.
assert.deepEqual(mover([1, 2, 3], 0, 1), [2, 1, 3])
assert.deepEqual(mover([1, 2, 3], 2, 1), [1, 2, 3])
assert.deepEqual(mover([1, 2, 3], 2, -2), [3, 1, 2])
assert.ok(mesmoLayout(layoutPadrao(), mesclarLayout(null)))

console.log("dashboard-layout: ok")
