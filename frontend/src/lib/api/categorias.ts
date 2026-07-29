import { useQuery } from "@tanstack/react-query"

import { api } from "@/lib/api/client"
import type { components } from "@/lib/api/schema"

export type Categoria = components["schemas"]["CategoriaRead"]

/** Taxonomia do Pluggy (read-only, §4.5). Fixa → cacheia "para sempre". */
export function useCategorias() {
  return useQuery({
    queryKey: ["categorias"],
    staleTime: Infinity,
    queryFn: async (): Promise<Categoria[]> => {
      const { data, error } = await api.GET("/api/categorias")
      if (error || !data) throw new Error("falha ao carregar categorias")
      return data
    },
  })
}

export function nomeCategoria(c: Categoria): string {
  return c.description_translated ?? c.description
}

/** Rótulo por `pluggy_id` (para exibir a categoria de uma transação). */
export function useMapaCategorias(): Map<string, string> {
  const { data } = useCategorias()
  return new Map((data ?? []).map((c) => [c.pluggy_id, nomeCategoria(c)]))
}
