import { useQuery } from "@tanstack/react-query"

import { api } from "@/lib/api/client"
import type { components } from "@/lib/api/schema"

export type IndicadorInfo = components["schemas"]["IndicadorInfo"]
export type IndicadorSerie = components["schemas"]["IndicadorSerie"]

/** Indicadores oferecidos (IBOV só aparece com token do brapi configurado no servidor). */
export function useIndicadores() {
  return useQuery({
    queryKey: ["indicadores"],
    queryFn: async (): Promise<IndicadorInfo[]> => {
      const { data, error } = await api.GET("/api/indicadores")
      if (error || !data) throw new Error("falha ao carregar os indicadores")
      return data
    },
  })
}

/** Séries normalizadas (% acumulado no período) dos indicadores escolhidos. */
export function useIndicadoresSerie(
  codigos: string[],
  periodo: { inicio: string; fim: string }
) {
  const chave = [...codigos].sort().join(",")
  return useQuery({
    queryKey: ["indicadores", "serie", chave, periodo.inicio, periodo.fim],
    enabled: codigos.length > 0,
    queryFn: async (): Promise<IndicadorSerie[]> => {
      const { data, error } = await api.GET("/api/indicadores/serie", {
        params: {
          query: { codigos: chave, inicio: periodo.inicio, fim: periodo.fim },
        },
      })
      if (error || !data) throw new Error("falha ao carregar os indicadores")
      return data
    },
  })
}
