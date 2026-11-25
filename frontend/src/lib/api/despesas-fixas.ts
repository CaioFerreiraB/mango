import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { api } from "@/lib/api/client"
import { mensagemErro } from "@/lib/api/erros"
import type { components } from "@/lib/api/schema"

export type DespesaFixa = components["schemas"]["DespesaFixaRead"]
export type DespesaFixaCreate = components["schemas"]["DespesaFixaCreate"]
export type DespesaFixaUpdate = components["schemas"]["DespesaFixaUpdate"]
export type DespesaFixaResumo = components["schemas"]["DespesaFixaResumo"]
export type Ocorrencia = components["schemas"]["OcorrenciaRead"]
export type Frequencia = DespesaFixaCreate["frequencia"]
export type SituacaoDespesa = DespesaFixa["situacao"]
export type SituacaoOcorrencia = Ocorrencia["situacao"]

export const despesasFixasKeys = {
  all: ["despesas-fixas"] as const,
  lista: ["despesas-fixas", "lista"] as const,
  resumo: ["despesas-fixas", "resumo"] as const,
  ocorrencias: (id: number) => ["despesas-fixas", id, "ocorrencias"] as const,
}

export function useDespesasFixas() {
  return useQuery({
    queryKey: despesasFixasKeys.lista,
    queryFn: async (): Promise<DespesaFixa[]> => {
      const { data, error } = await api.GET("/api/despesas-fixas")
      if (error || !data) throw new Error("falha ao carregar as despesas fixas")
      return data
    },
  })
}

/** Mês corrente: pagas/em aberto/atrasadas + próximos vencimentos (página e widget). */
export function useResumoDespesasFixas() {
  return useQuery({
    queryKey: despesasFixasKeys.resumo,
    queryFn: async (): Promise<DespesaFixaResumo> => {
      const { data, error } = await api.GET("/api/despesas-fixas/resumo")
      if (error || !data)
        throw new Error("falha ao carregar o resumo das despesas fixas")
      return data
    },
  })
}

export function useOcorrencias(id: number | null) {
  return useQuery({
    queryKey: despesasFixasKeys.ocorrencias(id ?? 0),
    enabled: id != null,
    queryFn: async (): Promise<Ocorrencia[]> => {
      const { data, error } = await api.GET(
        "/api/despesas-fixas/{despesa_id}/ocorrencias",
        { params: { path: { despesa_id: id! } } }
      )
      if (error || !data) throw new Error("falha ao carregar os vencimentos")
      return data
    },
  })
}

// Prefixo único: lista, resumo e vencimentos se revalidam juntos.
function invalidar(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: despesasFixasKeys.all })
}

export function useCriarDespesaFixa() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: DespesaFixaCreate): Promise<DespesaFixa> => {
      const { data, error } = await api.POST("/api/despesas-fixas", { body })
      if (error || !data)
        throw new Error(mensagemErro(error, "falha ao criar a despesa fixa"))
      return data
    },
    onSuccess: () => invalidar(qc),
  })
}

export function useAtualizarDespesaFixa() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (args: {
      id: number
      patch: DespesaFixaUpdate
    }): Promise<DespesaFixa> => {
      const { data, error } = await api.PATCH(
        "/api/despesas-fixas/{despesa_id}",
        {
          params: { path: { despesa_id: args.id } },
          body: args.patch,
        }
      )
      if (error || !data)
        throw new Error(mensagemErro(error, "falha ao salvar a despesa fixa"))
      return data
    },
    onSuccess: () => invalidar(qc),
  })
}

export function useRemoverDespesaFixa() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: number) => {
      const { error } = await api.DELETE("/api/despesas-fixas/{despesa_id}", {
        params: { path: { despesa_id: id } },
      })
      if (error) throw new Error("falha ao excluir a despesa fixa")
    },
    onSuccess: () => {
      invalidar(qc)
      qc.invalidateQueries({ queryKey: ["transacoes"] }) // vínculos viram null
    },
  })
}

/** Pagar à mão, pular o mês ou reabrir um vencimento. */
export function useAtualizarOcorrencia() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (args: {
      id: number
      status: Ocorrencia["status"]
    }): Promise<Ocorrencia> => {
      const { data, error } = await api.PATCH(
        "/api/despesas-fixas/ocorrencias/{ocorrencia_id}",
        {
          params: { path: { ocorrencia_id: args.id } },
          body: { status: args.status },
        }
      )
      if (error || !data) throw new Error("falha ao atualizar o vencimento")
      return data
    },
    onSuccess: () => invalidar(qc),
  })
}

export const FREQUENCIAS: { value: Frequencia; label: string }[] = [
  { value: "semanal", label: "Semanal" },
  { value: "quinzenal", label: "Quinzenal" },
  { value: "mensal", label: "Mensal" },
  { value: "trimestral", label: "Trimestral" },
  { value: "semestral", label: "Semestral" },
  { value: "anual", label: "Anual" },
]

export const rotuloFrequencia = (f: Frequencia) =>
  FREQUENCIAS.find((x) => x.value === f)?.label ?? f
