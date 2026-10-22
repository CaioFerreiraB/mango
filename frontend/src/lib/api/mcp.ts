import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { api } from "@/lib/api/client"
import { mensagemErro } from "@/lib/api/erros"
import type { components } from "@/lib/api/schema"

export type AcessoMcp = components["schemas"]["AcessoMcpRead"]
export type AcessoMcpUpdate = components["schemas"]["AcessoMcpUpdate"]

const chave = ["acesso-mcp"] as const

/** Estado do acesso de agentes via MCP (docs/mcp.md) — sem o token em claro. */
export function useAcessoMcp() {
  return useQuery({
    queryKey: chave,
    queryFn: async (): Promise<AcessoMcp> => {
      const { data, error } = await api.GET("/api/acesso-mcp")
      if (error || !data) throw new Error("falha ao carregar o acesso MCP")
      return data
    },
  })
}

/** Liga/desliga e troca a permissão. A primeira ativação gera o token no servidor. */
export function useAtualizarAcessoMcp() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (patch: AcessoMcpUpdate): Promise<AcessoMcp> => {
      const { data, error } = await api.PATCH("/api/acesso-mcp", {
        body: patch,
      })
      if (error || !data)
        throw new Error(mensagemErro(error, "falha ao salvar o acesso MCP"))
      return data
    },
    onSuccess: (data) => qc.setQueryData(chave, data),
  })
}

/** Busca o token em claro — só sob ação explícita do usuário (Mostrar/Copiar). */
export async function revelarTokenMcp(): Promise<string> {
  const { data, error } = await api.GET("/api/acesso-mcp/token")
  if (error || !data)
    throw new Error(mensagemErro(error, "falha ao obter o token"))
  return data.token
}

/** Gera um token novo; o anterior para de funcionar na hora. */
export function useTrocarTokenMcp() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (): Promise<string> => {
      const { data, error } = await api.POST("/api/acesso-mcp/trocar-token")
      if (error || !data)
        throw new Error(mensagemErro(error, "falha ao trocar o token"))
      return data.token
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: chave }),
  })
}
