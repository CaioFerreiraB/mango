import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { api } from "@/lib/api/client"
import type { components } from "@/lib/api/schema"

export type Assinatura = components["schemas"]["AssinaturaRead"]
export type AssinaturaCreate = components["schemas"]["AssinaturaCreate"]
export type AssinaturaUpdate = components["schemas"]["AssinaturaUpdate"]
export type AssinaturaResumo = components["schemas"]["AssinaturaResumoRead"]
export type AssinaturaCandidato = components["schemas"]["AssinaturaCandidatoRead"]
export type Periodicidade = AssinaturaCreate["periodicidade"]

export const assinaturasKeys = {
  all: ["assinaturas"] as const,
  resumo: ["assinaturas", "resumo"] as const,
  candidatos: ["assinaturas", "candidatos"] as const,
}

export function useAssinaturas() {
  return useQuery({
    queryKey: assinaturasKeys.all,
    queryFn: async (): Promise<Assinatura[]> => {
      const { data, error } = await api.GET("/api/assinaturas")
      if (error || !data) throw new Error("falha ao carregar as assinaturas")
      return data
    },
  })
}

/** Total mensal, total por categoria e lista de vigentes (§4.7). */
export function useResumoAssinaturas() {
  return useQuery({
    queryKey: assinaturasKeys.resumo,
    queryFn: async (): Promise<AssinaturaResumo> => {
      const { data, error } = await api.GET("/api/assinaturas/resumo")
      if (error || !data) throw new Error("falha ao carregar o resumo de assinaturas")
      return data
    },
  })
}

/** Busca sob demanda de candidatas a assinatura (§4.7). `enabled` liga só com o dialog aberto; sem
 *  cache (`staleTime`/`gcTime` 0) para cada abertura refazer a busca do zero. */
export function useCandidatosAssinatura(enabled: boolean) {
  return useQuery({
    queryKey: assinaturasKeys.candidatos,
    enabled,
    staleTime: 0,
    gcTime: 0,
    queryFn: async (): Promise<AssinaturaCandidato[]> => {
      const { data, error } = await api.GET("/api/assinaturas/candidatos")
      if (error || !data) throw new Error("falha ao buscar assinaturas")
      return data
    },
  })
}

function invalidar(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: assinaturasKeys.all })
}

/** Cria várias assinaturas de uma vez (candidatas confirmadas). Reusa o POST unitário; tolera falha
 *  parcial (`allSettled`) e invalida uma vez só. Retorna quantas criou/falharam. */
export function useCriarAssinaturasEmLote() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (bodies: AssinaturaCreate[]) => {
      const res = await Promise.allSettled(
        bodies.map((body) => api.POST("/api/assinaturas", { body }))
      )
      const criadas = res.filter(
        (r) => r.status === "fulfilled" && !r.value.error
      ).length
      return { criadas, falhas: bodies.length - criadas }
    },
    onSuccess: () => invalidar(qc),
  })
}

export function useCriarAssinatura() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: AssinaturaCreate): Promise<Assinatura> => {
      const { data, error } = await api.POST("/api/assinaturas", { body })
      if (error || !data) throw new Error("falha ao criar a assinatura")
      return data
    },
    onSuccess: () => invalidar(qc),
  })
}

export function useAtualizarAssinatura() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (args: { id: number; patch: AssinaturaUpdate }): Promise<Assinatura> => {
      const { data, error } = await api.PATCH("/api/assinaturas/{item_id}", {
        params: { path: { item_id: args.id } },
        body: args.patch,
      })
      if (error || !data) throw new Error("falha ao salvar a assinatura")
      return data
    },
    onSuccess: () => invalidar(qc),
  })
}

export function useRemoverAssinatura() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: number) => {
      const { error } = await api.DELETE("/api/assinaturas/{item_id}", {
        params: { path: { item_id: id } },
      })
      if (error) throw new Error("falha ao remover a assinatura")
    },
    onSuccess: () => invalidar(qc),
  })
}
