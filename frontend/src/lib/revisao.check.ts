/**
 * Self-check puro do estado de revisão (sem framework). Rodar de `frontend/`:
 *   npx --yes tsx@4 src/lib/revisao.check.ts
 */
import assert from "node:assert/strict"

import { deveGravarNoBlur, estadoRevisao } from "@/lib/revisao"

// Sem corte definido, "não revisada" é sempre pendente — comportamento anterior ao campo.
assert.equal(
  estadoRevisao(false, "2019-01-05T12:00:00Z", null),
  "pendente",
  "sem corte: transação antiga continua pendente"
)
assert.equal(
  estadoRevisao(false, "2026-03-10T12:00:00Z", undefined),
  "pendente",
  "corte ainda carregando (undefined) não ignora nada"
)

// Revisada é revisada, mesmo antes do corte — o corte nunca desfaz uma decisão do usuário.
assert.equal(
  estadoRevisao(true, "2019-01-05T12:00:00Z", "2026-03-01"),
  "revisado",
  "revisada antes do corte continua revisada"
)

// O corte é inclusivo: o próprio dia escolhido já pede revisão.
assert.equal(
  estadoRevisao(false, "2026-03-01T12:00:00Z", "2026-03-01"),
  "pendente",
  "o dia do corte entra na fila"
)
assert.equal(
  estadoRevisao(false, "2026-02-28T12:00:00Z", "2026-03-01"),
  "ignorado",
  "véspera do corte é ignorada"
)

// Fuso: 01/03 02:00 UTC é 28/02 23:00 em São Paulo → cai ANTES do corte de 01/03.
assert.equal(
  estadoRevisao(false, "2026-03-01T02:00:00Z", "2026-03-01"),
  "ignorado",
  "madrugada UTC pertence ao dia anterior em SP"
)
// E 01/03 03:00 UTC já é 00:00 de 01/03 em SP → entra na fila.
assert.equal(
  estadoRevisao(false, "2026-03-01T03:00:00Z", "2026-03-01"),
  "pendente",
  "meia-noite em SP já é o dia do corte"
)

// Virada de ano — a comparação lexicográfica de `yyyy-mm-dd` tem de respeitar a cronologia.
assert.equal(
  estadoRevisao(false, "2025-12-31T15:00:00Z", "2026-01-01"),
  "ignorado",
  "31/12 é anterior a 01/01 do ano seguinte"
)

console.log("revisao.check.ts OK")

// --- guarda do blur no card de configurações -------------------------------------------
// Regressão real (47d571c): a guarda era `relatedTarget === limpar.current`. Sem data salva o botão
// "Limpar" não é renderizado (ref nula) e clicar em área não-focável dá relatedTarget nulo, então
// `null === null` engolia a PRIMEIRA gravação — justamente a que importa.
const botao = {} as EventTarget
assert.equal(
  deveGravarNoBlur(null, null),
  true,
  "sem data salva (ref nula) + clique em área não-focável: TEM de gravar"
)
assert.equal(
  deveGravarNoBlur(botao, botao),
  false,
  "foco indo para o botão Limpar: não grava (evita a corrida)"
)
assert.equal(
  deveGravarNoBlur({} as EventTarget, botao),
  true,
  "foco indo para outro elemento: grava normalmente"
)
assert.equal(
  deveGravarNoBlur(null, botao),
  true,
  "com data salva + clique em área não-focável: grava"
)

console.log("guarda do blur OK")
