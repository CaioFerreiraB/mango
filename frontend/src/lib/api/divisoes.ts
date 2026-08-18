import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { api } from "@/lib/api/client"
import { mensagemErro } from "@/lib/api/erros"
import type { components } from "@/lib/api/schema"

export type DivisaoDespesa = components["schemas"]["DivisaoDespesaRead"]
export type DivisaoDespesaCreate = components["schemas"]["DivisaoDespesaCreate"]
export type DivisaoDespesaUpdate = components["schemas"]["DivisaoDespesaUpdate"]
export type ResumoDivisoes = components["schemas"]["ResumoDivisoes"]
export type PessoaDivisao = components["schemas"]["PessoaDivisao"]
export type ModoDivisao = DivisaoDespesaCreate["modo_divisao"]
/** Espelha `EscopoDivisao` do backend (app/schemas/divisao.py) — não é um schema nomeado no
 *  OpenAPI (é só um parâmetro de query), então não dá pra derivar do `components`. */
export type EscopoDivisao = "todas" | "minhas" | "comigo" | "arquivadas"

export const divisoesKeys = {
  all: ["divisoes"] as const,
  lista: (escopo: EscopoDivisao) => ["divisoes", "lista", escopo] as const,
  detalhe: (id: number) => ["divisoes", id] as const,
  resumo: ["divisoes", "resumo"] as const,
  pessoas: ["divisoes", "pessoas"] as const,
}

function invalidar(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: divisoesKeys.all })
  qc.invalidateQueries({ queryKey: divisoesKeys.resumo })
  qc.invalidateQueries({ queryKey: divisoesKeys.pessoas })
}

export function useResumoDivisoes() {
  return useQuery({
    queryKey: divisoesKeys.resumo,
    queryFn: async (): Promise<ResumoDivisoes> => {
      const { data, error } = await api.GET("/api/divisoes-despesa/resumo")
      if (error || !data)
        throw new Error("falha ao carregar o resumo das divisões")
      return data
    },
  })
}

export function usePessoasDivisao() {
  return useQuery({
    queryKey: divisoesKeys.pessoas,
    queryFn: async (): Promise<PessoaDivisao[]> => {
      const { data, error } = await api.GET("/api/divisoes-despesa/pessoas")
      if (error || !data) throw new Error("falha ao carregar as pessoas")
      return data
    },
  })
}

export function useDivisoes(escopo: EscopoDivisao = "todas") {
  return useQuery({
    queryKey: divisoesKeys.lista(escopo),
    queryFn: async (): Promise<DivisaoDespesa[]> => {
      const { data, error } = await api.GET("/api/divisoes-despesa", {
        params: { query: { escopo } },
      })
      if (error || !data) throw new Error("falha ao carregar as divisões")
      return data
    },
  })
}

export function useDivisao(id: number | null) {
  return useQuery({
    queryKey: divisoesKeys.detalhe(id ?? 0),
    queryFn: async (): Promise<DivisaoDespesa> => {
      const { data, error } = await api.GET(
        "/api/divisoes-despesa/{despesa_id}",
        {
          params: { path: { despesa_id: id! } },
        }
      )
      if (error || !data) throw new Error("falha ao carregar a divisão")
      return data
    },
    enabled: id !== null,
  })
}

export function useCriarDivisao() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: DivisaoDespesaCreate): Promise<DivisaoDespesa> => {
      const { data, error } = await api.POST("/api/divisoes-despesa", { body })
      if (error || !data)
        throw new Error(mensagemErro(error, "falha ao criar a divisão"))
      return data
    },
    onSuccess: () => invalidar(qc),
  })
}

export function useAtualizarDivisao() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (args: {
      id: number
      patch: DivisaoDespesaUpdate
    }): Promise<DivisaoDespesa> => {
      const { data, error } = await api.PATCH(
        "/api/divisoes-despesa/{despesa_id}",
        {
          params: { path: { despesa_id: args.id } },
          body: args.patch,
        }
      )
      if (error || !data)
        throw new Error(mensagemErro(error, "falha ao salvar a divisão"))
      return data
    },
    onSuccess: (_data, args) => {
      invalidar(qc)
      qc.invalidateQueries({ queryKey: divisoesKeys.detalhe(args.id) })
    },
  })
}

export function useExcluirDivisao() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: number) => {
      const { error } = await api.DELETE("/api/divisoes-despesa/{despesa_id}", {
        params: { path: { despesa_id: id } },
      })
      if (error)
        throw new Error(mensagemErro(error, "falha ao excluir a divisão"))
    },
    onSuccess: () => invalidar(qc),
  })
}

function useMarcarQuitada(path: "quitar" | "reabrir") {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: number): Promise<DivisaoDespesa> => {
      const rota =
        path === "quitar"
          ? ("/api/divisoes-despesa/{despesa_id}/quitar" as const)
          : ("/api/divisoes-despesa/{despesa_id}/reabrir" as const)
      const { data, error } = await api.POST(rota, {
        params: { path: { despesa_id: id } },
      })
      if (error || !data)
        throw new Error(mensagemErro(error, "falha ao atualizar a divisão"))
      return data
    },
    onSuccess: (_data, id) => {
      invalidar(qc)
      qc.invalidateQueries({ queryKey: divisoesKeys.detalhe(id) })
    },
  })
}

export function useQuitarDivisao() {
  return useMarcarQuitada("quitar")
}

export function useReabrirDivisao() {
  return useMarcarQuitada("reabrir")
}
