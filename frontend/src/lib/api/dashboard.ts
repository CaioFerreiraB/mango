import { useQuery } from "@tanstack/react-query"

import { api } from "@/lib/api/client"
import type { components } from "@/lib/api/schema"

export type DashboardResumo = components["schemas"]["DashboardResumo"]
export type GastoCategoria = components["schemas"]["GastoCategoria"]
export type DashboardSeries = components["schemas"]["DashboardSeries"]
export type SerieBucket = components["schemas"]["SerieBucket"]
export type Granularidade = "diaria" | "semanal" | "mensal"

/** Agregados do período (§4.10). Sem `inicio/fim` o backend usa o mês corrente (fuso SP). */
export function useDashboard(periodo?: { inicio?: string; fim?: string }) {
  return useQuery({
    queryKey: ["dashboard", periodo?.inicio ?? null, periodo?.fim ?? null],
    queryFn: async (): Promise<DashboardResumo> => {
      const { data, error } = await api.GET("/api/dashboard", {
        params: { query: { inicio: periodo?.inicio, fim: periodo?.fim } },
      })
      if (error || !data) throw new Error("falha ao carregar o dashboard")
      return data
    },
  })
}

/** Série temporal (semanal/mensal) de entradas/saídas/resultado e gasto por categoria. */
export function useDashboardSeries(
  periodo: { inicio?: string; fim?: string } | undefined,
  granularidade: Granularidade
) {
  return useQuery({
    queryKey: [
      "dashboard-series",
      periodo?.inicio ?? null,
      periodo?.fim ?? null,
      granularidade,
    ],
    queryFn: async (): Promise<DashboardSeries> => {
      const { data, error } = await api.GET("/api/dashboard/series", {
        params: {
          query: { inicio: periodo?.inicio, fim: periodo?.fim, granularidade },
        },
      })
      if (error || !data)
        throw new Error("falha ao carregar a série do dashboard")
      return data
    },
  })
}
