import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { api } from "@/lib/api/client"
import { mensagemErro } from "@/lib/api/erros"
import type { components } from "@/lib/api/schema"
import { criarParserSSE } from "@/lib/sse"

export type ConversaResumo = components["schemas"]["ConversaIaResumo"]
export type Conversa = components["schemas"]["ConversaIaRead"]
export type MensagemChat = components["schemas"]["MensagemIaRead"]
export type Proposta = components["schemas"]["PropostaIa"]

/** Eventos do `POST /api/ia/mensagens` (docs/dev/chat-web.md, WSTREAM01). */
export type EventoChat =
  | { tipo: "conversa"; dados: { id: number; titulo: string } }
  | { tipo: "status"; dados: { texto: string } }
  | { tipo: "delta"; dados: { texto: string } }
  | { tipo: "fim"; dados: { mensagem_id: number | null } }
  | { tipo: "proposta"; dados: Proposta }
  | { tipo: "aplicada"; dados: { resultado: string } }
  | { tipo: "erro"; dados: { mensagem: string } }

export const chaveConversas = ["ia", "conversas"] as const

export function usePreferenciaIa() {
  return useQuery({
    queryKey: ["ia", "preferencias"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/ia/preferencias")
      if (error || !data)
        throw new Error(mensagemErro(error, "Falha ao carregar a IA."))
      return data
    },
  })
}

export function useConversas(habilitado: boolean) {
  return useQuery({
    queryKey: chaveConversas,
    enabled: habilitado,
    queryFn: async () => {
      const { data, error } = await api.GET("/api/ia/conversas")
      if (error || !data)
        throw new Error(mensagemErro(error, "Falha ao carregar as conversas."))
      return data
    },
  })
}

export function useConversa(id: number | null, acompanhar: boolean) {
  return useQuery({
    queryKey: [...chaveConversas, id],
    enabled: id !== null,
    // Resposta em andamento sem stream local (recarregou/saiu): acompanha até o servidor salvar.
    refetchInterval: (q) =>
      acompanhar && q.state.data?.executando ? 2000 : false,
    queryFn: async () => {
      const { data, error } = await api.GET("/api/ia/conversas/{conversa_id}", {
        params: { path: { conversa_id: id! } },
      })
      if (error || !data)
        throw new Error(mensagemErro(error, "Falha ao carregar a conversa."))
      return data
    },
  })
}

function useInvalidar() {
  const qc = useQueryClient()
  return () => qc.invalidateQueries({ queryKey: chaveConversas })
}

export function useRenomearConversa() {
  const invalidar = useInvalidar()
  return useMutation({
    mutationFn: async ({ id, titulo }: { id: number; titulo: string }) => {
      const { error } = await api.PATCH("/api/ia/conversas/{conversa_id}", {
        params: { path: { conversa_id: id } },
        body: { titulo },
      })
      if (error) throw new Error(mensagemErro(error, "Falha ao renomear."))
    },
    onSuccess: invalidar,
  })
}

/** `antes` roda antes de limpar o cache: quem mostra a conversa sai dela, sem refetch (404). */
export function useExcluirConversa(antes: () => void) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: number) => {
      const { error } = await api.DELETE("/api/ia/conversas/{conversa_id}", {
        params: { path: { conversa_id: id } },
      })
      if (error) throw new Error(mensagemErro(error, "Falha ao excluir."))
    },
    onSuccess: (_, id) => {
      antes()
      qc.removeQueries({ queryKey: [...chaveConversas, id] })
      return qc.invalidateQueries({ queryKey: chaveConversas, exact: true })
    },
  })
}

export function useDecidirProposta() {
  const invalidar = useInvalidar()
  return useMutation({
    mutationFn: async ({
      id,
      confirmar,
    }: {
      id: string
      confirmar: boolean
    }) => {
      const params = { path: { operacao_id: id } }
      const { error } = confirmar
        ? await api.POST("/api/ia/operacoes/{operacao_id}/confirmar", {
            params,
          })
        : await api.POST("/api/ia/operacoes/{operacao_id}/cancelar", { params })
      if (error)
        throw new Error(
          mensagemErro(error, "Não foi possível concluir a alteração.")
        )
    },
    onSettled: invalidar,
  })
}

export async function pararResposta() {
  await api.POST("/api/ia/execucao/parar")
}

/**
 * Envia (ou regenera) e repassa cada evento SSE. Passa pelo cliente tipado, então herda o CSRF.
 * Erros antes do stream (409 em andamento, 429 cota, 404) viram exceção com o `detail`.
 */
export async function transmitirMensagem(
  body: components["schemas"]["MensagemIaCreate"],
  signal: AbortSignal,
  onEvento: (evento: EventoChat) => void
) {
  const { response, error } = await api.POST("/api/ia/mensagens", {
    body,
    signal,
    parseAs: "stream",
  })
  if (error || !response.ok || !response.body)
    throw new Error(mensagemErro(error, "Não foi possível enviar a mensagem."))
  const alimentar = criarParserSSE((tipo, dados) =>
    onEvento({ tipo, dados } as EventoChat)
  )
  const leitor = response.body.pipeThrough(new TextDecoderStream()).getReader()
  for (;;) {
    const { value, done } = await leitor.read()
    if (done) return
    alimentar(value)
  }
}
