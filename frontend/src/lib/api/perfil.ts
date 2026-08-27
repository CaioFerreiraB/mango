import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { api } from "@/lib/api/client"
import { mensagemErro } from "@/lib/api/erros"
import type { components } from "@/lib/api/schema"

export type Perfil = components["schemas"]["PerfilRead"]
export type PerfilUpdate = components["schemas"]["PerfilUpdate"]

export function usePerfil() {
  return useQuery({
    queryKey: ["perfil"],
    queryFn: async (): Promise<Perfil> => {
      const { data, error } = await api.GET("/api/perfil")
      if (error || !data) throw new Error("falha ao carregar o perfil")
      return data
    },
  })
}

export function useAtualizarPerfil() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (patch: PerfilUpdate): Promise<Perfil> => {
      const { data, error } = await api.PATCH("/api/perfil", { body: patch })
      if (error || !data)
        throw new Error(mensagemErro(error, "falha ao salvar o perfil"))
      return data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["perfil"] })
      qc.invalidateQueries({ queryKey: ["me"] })
    },
  })
}

/** Grava o token brapi (write-only, cifrado no servidor; nunca é devolvido). */
export function useDefinirBrapiToken() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (token: string): Promise<void> => {
      const { error } = await api.PUT("/api/perfil/brapi-token", {
        body: { token },
      })
      if (error) throw new Error(mensagemErro(error, "falha ao salvar o token"))
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["perfil"] }),
  })
}

/** Remove o token brapi. */
export function useRemoverBrapiToken() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (): Promise<void> => {
      const { error } = await api.DELETE("/api/perfil/brapi-token")
      if (error)
        throw new Error(mensagemErro(error, "falha ao remover o token"))
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["perfil"] }),
  })
}

/** Testa o token brapi guardado contra a brapi. */
export function useTestarBrapiToken() {
  return useMutation({
    mutationFn: async (): Promise<boolean> => {
      const { data, error } = await api.POST("/api/perfil/brapi-token/testar")
      if (error || !data) throw new Error("não foi possível testar agora")
      return data.valida
    },
  })
}
