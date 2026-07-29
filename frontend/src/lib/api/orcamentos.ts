import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { api } from "@/lib/api/client"
import type { components } from "@/lib/api/schema"

export type Orcamento = components["schemas"]["OrcamentoRead"]
export type OrcamentoCreate = components["schemas"]["OrcamentoCreate"]
export type OrcamentoUpdate = components["schemas"]["OrcamentoUpdate"]
export type OrcamentoConsumo = components["schemas"]["OrcamentoConsumoRead"]
export type OrcamentoConsumoItem = components["schemas"]["OrcamentoConsumoItem"]

export const orcamentosKeys = {
  all: ["orcamentos"] as const,
  consumo: (ano: number, mes: number) => ["orcamentos", "consumo", ano, mes] as const,
}

/** Consumo e alertas (50/75/90/100%) dos orçamentos do mês (§4.6). */
export function useConsumoOrcamentos(ano: number, mes: number) {
  return useQuery({
    queryKey: orcamentosKeys.consumo(ano, mes),
    queryFn: async (): Promise<OrcamentoConsumo> => {
      const { data, error } = await api.GET("/api/orcamentos/consumo", {
        params: { query: { ano, mes } },
      })
      if (error || !data) throw new Error("falha ao carregar o consumo dos orçamentos")
      return data
    },
  })
}

function invalidar(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: orcamentosKeys.all })
  qc.invalidateQueries({ queryKey: ["dashboard"] })
}

export function useCriarOrcamento() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: OrcamentoCreate): Promise<Orcamento> => {
      const { data, error } = await api.POST("/api/orcamentos", { body })
      if (error || !data) throw new Error("falha ao criar o orçamento")
      return data
    },
    onSuccess: () => invalidar(qc),
  })
}

/** Edita o limite **do mês** (linha materializada), não o padrão do orçamento. */
export function useAtualizarLimiteMensal() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (args: { id: number; limite_centavos: number }) => {
      const { data, error } = await api.PATCH("/api/orcamentos-mensais/{item_id}", {
        params: { path: { item_id: args.id } },
        body: { limite_centavos: args.limite_centavos, editado_manualmente: true },
      })
      if (error || !data) throw new Error("falha ao salvar o limite do mês")
      return data
    },
    onSuccess: () => invalidar(qc),
  })
}

export function useRemoverOrcamento() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: number) => {
      const { error } = await api.DELETE("/api/orcamentos/{orcamento_id}", {
        params: { path: { orcamento_id: id } },
      })
      if (error) throw new Error("falha ao remover o orçamento")
    },
    onSuccess: () => invalidar(qc),
  })
}
