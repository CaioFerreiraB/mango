import { useQuery } from "@tanstack/react-query"

import { api } from "@/lib/api/client"
import type { components } from "@/lib/api/schema"

export type Fatura = components["schemas"]["FaturaRead"]

export function useFaturas() {
  return useQuery({
    queryKey: ["faturas"],
    queryFn: async (): Promise<Fatura[]> => {
      const { data, error } = await api.GET("/api/faturas")
      if (error || !data) throw new Error("falha ao carregar faturas")
      return data
    },
  })
}

export function useFatura(faturaId: number) {
  return useQuery({
    queryKey: ["faturas", faturaId],
    queryFn: async (): Promise<Fatura> => {
      // A factory read-only nomeia o path param genericamente como `item_id`.
      const { data, error } = await api.GET("/api/faturas/{item_id}", {
        params: { path: { item_id: faturaId } },
      })
      if (error || !data) throw new Error("falha ao carregar a fatura")
      return data
    },
  })
}
