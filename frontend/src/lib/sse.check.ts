/**
 * Self-check do parser SSE do chat (sem framework). Rodar de `frontend/`:
 *   npx --yes tsx@4 src/lib/sse.check.ts
 */
import assert from "node:assert/strict"

import { criarParserSSE } from "@/lib/sse"

const recebidos: [string, unknown][] = []
const alimentar = criarParserSSE((tipo, dados) => recebidos.push([tipo, dados]))

// Evento partido no meio do JSON e do separador; heartbeat no meio não vira evento.
alimentar('event: conversa\ndata: {"id": 1, "tit')
alimentar('ulo": "oi"}\n')
alimentar("\n: ping\n\n")
alimentar(
  'event: delta\r\ndata: {"texto": "a\\nb"}\r\n\r\nevent: fim\ndata: {"mensagem_id": 2}\n\n'
)
// Incompleto: fica no buffer até o separador chegar.
alimentar('event: erro\ndata: {"mensagem": "x"}\n')

assert.deepEqual(recebidos, [
  ["conversa", { id: 1, titulo: "oi" }],
  ["delta", { texto: "a\nb" }],
  ["fim", { mensagem_id: 2 }],
])
alimentar("\n")
assert.deepEqual(recebidos.at(-1), ["erro", { mensagem: "x" }])

// `data` em várias linhas é juntado com \n (spec SSE).
const multi: unknown[] = []
criarParserSSE((_, d) => multi.push(d))('data: {"a":\ndata: 1}\n\n')
assert.deepEqual(multi, [{ a: 1 }])

console.log("sse.check: ok")
