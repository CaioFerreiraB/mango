import { useMutation, useQuery } from "@tanstack/react-query"

import { api } from "@/lib/api/client"
import { mensagemErro } from "@/lib/api/erros"
import type { components } from "@/lib/api/schema"

export type ConviteStatus = components["schemas"]["ConviteStatus"]
export type IniciarConviteResponse =
  components["schemas"]["IniciarConviteResponse"]
export type Me = components["schemas"]["MeRead"]

/** Convite de pessoa "só divisão" (§4.11) — fluxo público, mesmo desenho de 2 passos do
 *  first-run setup (`@/lib/api/auth`), mas o usuário já existe (placeholder) desde o convite. */
export function useConviteStatus(token: string) {
  return useQuery({
    queryKey: ["convite", token],
    queryFn: async (): Promise<ConviteStatus> => {
      const { data, error } = await api.GET("/api/convites/{token}", {
        params: { path: { token } },
      })
      if (error || !data) throw new Error("convite não encontrado")
      return data
    },
    retry: false,
  })
}

/** Passo 1: gera o TOTP + ticket cifrado (nada é gravado ainda). 2FA é opcional (§5.2, #15) —
 *  com `ativar_totp: false` o passo 1 já volta sem segredo, pra pular direto pro passo 2. */
export function useIniciarConvite(token: string) {
  return useMutation({
    mutationFn: async (args: {
      senha: string
      ativar_totp: boolean
    }): Promise<IniciarConviteResponse> => {
      const { data, error } = await api.POST("/api/convites/{token}", {
        params: { path: { token } },
        body: args,
      })
      if (error || !data)
        throw new Error(mensagemErro(error, "falha ao iniciar o cadastro"))
      return data
    },
  })
}

/** Passo 2: confirma o código do autenticador (quando há) — grava senha/TOTP e já loga. */
export function useConfirmarConvite() {
  return useMutation({
    mutationFn: async (args: {
      ticket: string
      codigo_totp?: string
    }): Promise<Me> => {
      const { data, error } = await api.POST("/api/convites/confirmar", {
        body: args,
      })
      if (error || !data)
        throw new Error(mensagemErro(error, "código incorreto"))
      return data
    },
  })
}
