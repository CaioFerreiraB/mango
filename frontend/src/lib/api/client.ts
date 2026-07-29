import createClient from "openapi-fetch"

import type { paths } from "@/lib/api/schema"

/**
 * Cliente HTTP tipado a partir do schema OpenAPI do backend (gerado em `schema.d.ts`).
 *
 * `baseUrl` vazio = mesma origem. Em dev o Vite faz proxy de `/api` → `:8000`; em produção o
 * FastAPI serve a SPA e a API juntos. Os caminhos do schema já carregam o prefixo `/api`, então
 * basta uma origem (ou `VITE_API_BASE_URL` para apontar a um backend remoto em dev).
 */
export const api = createClient<paths>({
  baseUrl: import.meta.env.VITE_API_BASE_URL ?? "",
})

const MUTACOES = new Set(["POST", "PUT", "PATCH", "DELETE"])

function csrfCookie(): string | undefined {
  return document.cookie
    .split("; ")
    .find((c) => c.startsWith("mango_csrf="))
    ?.slice("mango_csrf=".length)
}

/**
 * CSRF double-submit (§5.2): ecoa o cookie `mango_csrf` no header `X-CSRF-Token` nas mutações. No
 * modo local não há cookie e o backend não exige — o header simplesmente não é adicionado.
 */
api.use({
  onRequest({ request }) {
    if (MUTACOES.has(request.method)) {
      const token = csrfCookie()
      if (token) request.headers.set("X-CSRF-Token", decodeURIComponent(token))
    }
    return request
  },
})
