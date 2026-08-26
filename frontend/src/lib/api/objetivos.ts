import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { api } from "@/lib/api/client"
import type { components } from "@/lib/api/schema"

export type Objetivo = components["schemas"]["ObjetivoRead"]
export type ObjetivoDetalhe = components["schemas"]["ObjetivoDetalheRead"]
export type ObjetivoVinculo = components["schemas"]["ObjetivoVinculo"]
export type ObjetivoCreate = components["schemas"]["ObjetivoCreate"]
export type ObjetivoUpdate = components["schemas"]["ObjetivoUpdate"]

export const objetivosKeys = {
  all: ["objetivos"] as const,
  detalhe: (id: number) => ["objetivos", id] as const,
}

export function useObjetivos() {
  return useQuery({
    queryKey: objetivosKeys.all,
    queryFn: async (): Promise<Objetivo[]> => {
      const { data, error } = await api.GET("/api/objetivos")
      if (error || !data) throw new Error("falha ao carregar os objetivos")
      return data
    },
  })
}

export function useObjetivo(id: number) {
  return useQuery({
    queryKey: objetivosKeys.detalhe(id),
    queryFn: async (): Promise<ObjetivoDetalhe> => {
      const { data, error } = await api.GET("/api/objetivos/{objetivo_id}", {
        params: { path: { objetivo_id: id } },
      })
      if (error || !data) throw new Error("falha ao carregar o objetivo")
      return data
    },
  })
}

function invalidar(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: objetivosKeys.all })
}

export function useCriarObjetivo() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: ObjetivoCreate): Promise<Objetivo> => {
      const { data, error } = await api.POST("/api/objetivos", { body })
      if (error || !data) throw new Error("falha ao criar o objetivo")
      return data
    },
    onSuccess: () => invalidar(qc),
  })
}

export function useAtualizarObjetivo() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (args: {
      id: number
      patch: ObjetivoUpdate
    }): Promise<Objetivo> => {
      const { data, error } = await api.PATCH("/api/objetivos/{objetivo_id}", {
        params: { path: { objetivo_id: args.id } },
        body: args.patch,
      })
      if (error || !data) throw new Error("falha ao salvar o objetivo")
      return data
    },
    onSuccess: (_data, args) => {
      invalidar(qc)
      qc.invalidateQueries({ queryKey: objetivosKeys.detalhe(args.id) })
    },
  })
}

export function useRemoverObjetivo() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: number) => {
      const { error } = await api.DELETE("/api/objetivos/{objetivo_id}", {
        params: { path: { objetivo_id: id } },
      })
      if (error) throw new Error("falha ao remover o objetivo")
    },
    onSuccess: () => invalidar(qc),
  })
}

/** Vincula/desvincula uma conta a um objetivo (§4.8; 1:1-máx pelo lado da conta). */
export function useVincularConta() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (args: {
      contaId: number
      objetivoId: number | null
    }) => {
      const { error } = await api.PATCH("/api/contas/{conta_id}", {
        params: { path: { conta_id: args.contaId } },
        body: { objetivo_id: args.objetivoId },
      })
      if (error) throw new Error("falha ao vincular a conta")
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: objetivosKeys.all })
      qc.invalidateQueries({ queryKey: ["objetivos"] })
      qc.invalidateQueries({ queryKey: ["contas"] })
    },
  })
}

/** Vincula/desvincula um investimento a um objetivo (§4.8). */
export function useVincularInvestimento() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (args: {
      investimentoId: number
      objetivoId: number | null
    }) => {
      const { error } = await api.PATCH(
        "/api/investimentos/{investimento_id}",
        {
          params: { path: { investimento_id: args.investimentoId } },
          body: { objetivo_id: args.objetivoId },
        }
      )
      if (error) throw new Error("falha ao vincular o investimento")
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["objetivos"] })
      qc.invalidateQueries({ queryKey: ["investimentos"] })
    },
  })
}
