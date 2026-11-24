import { useRef } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { api } from "@/lib/api/client"
import { mensagemErro } from "@/lib/api/erros"
import type { components } from "@/lib/api/schema"
import type { Transacao } from "@/lib/api/transacoes"

export type DivisaoDespesa = components["schemas"]["DivisaoDespesaRead"]
export type DivisaoDespesaCreate = components["schemas"]["DivisaoDespesaCreate"]
export type DivisaoDespesaUpdate = components["schemas"]["DivisaoDespesaUpdate"]
export type ResumoDivisoes = components["schemas"]["ResumoDivisoes"]
export type PessoaDivisao = components["schemas"]["PessoaDivisao"]
export type ModoDivisao = DivisaoDespesaCreate["modo_divisao"]
/** Espelha `EscopoDivisao` do backend (app/schemas/divisao.py) — não é um schema nomeado no
 *  OpenAPI (é só um parâmetro de query), então não dá pra derivar do `components`. */
export type EscopoDivisao =
  "todas" | "minhas" | "comigo" | "arquivadas" | "sem_transacao"
export type DivisaoVinculo = components["schemas"]["DivisaoVinculo"]
export type ParteDivisao = components["schemas"]["ParteDivisao"]

export const ROTULO_MODO: Record<ModoDivisao, string> = {
  igualmente: "Dividir igualmente",
  porcentagem: "Por porcentagem",
  valor: "Por valor",
  integral: "Valor integral",
}

/** Modos em que cada pessoa tem a sua fatia digitada (`partes`). */
export const MODOS_COM_PARTES: ModoDivisao[] = ["porcentagem", "valor"]

export const divisoesKeys = {
  all: ["divisoes"] as const,
  lista: (escopo: EscopoDivisao) => ["divisoes", "lista", escopo] as const,
  detalhe: (id: number) => ["divisoes", id] as const,
  resumo: ["divisoes", "resumo"] as const,
  pessoas: ["divisoes", "pessoas"] as const,
}

/** Divisão mexe também na lista de transações (lançamentos/marcador) e no que conta como gasto
 *  do usuário — orçamento e dashboard usam só a parte dele. */
function invalidar(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: divisoesKeys.all })
  qc.invalidateQueries({ queryKey: divisoesKeys.resumo })
  qc.invalidateQueries({ queryKey: divisoesKeys.pessoas })
  qc.invalidateQueries({ queryKey: ["transacoes"] })
  qc.invalidateQueries({ queryKey: ["orcamentos"] })
  qc.invalidateQueries({ queryKey: ["dashboard"] })
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

export function useDivisoes(escopo: EscopoDivisao = "todas", enabled = true) {
  return useQuery({
    queryKey: divisoesKeys.lista(escopo),
    enabled,
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
  const tentativa = useRef({ corpo: "", chave: "" })
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: DivisaoDespesaCreate): Promise<DivisaoDespesa> => {
      const corpo = JSON.stringify(body)
      if (tentativa.current.corpo !== corpo)
        tentativa.current = { corpo, chave: crypto.randomUUID() }
      const { data, error } = await api.POST("/api/divisoes-despesa", {
        body,
        params: { header: { "idempotency-key": tentativa.current.chave } },
      })
      if (error || !data)
        throw new Error(mensagemErro(error, "falha ao criar a divisão"))
      return data
    },
    onSuccess: () => {
      tentativa.current = { corpo: "", chave: "" }
      invalidar(qc)
    },
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

/** Vincula/desvincula a transação do pagador ou marca "paguei fora do banco". */
export function useDefinirVinculo() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (args: {
      id: number
      vinculo: Omit<DivisaoVinculo, "reajustar"> & { reajustar?: boolean }
    }): Promise<DivisaoDespesa> => {
      const { data, error } = await api.PUT(
        "/api/divisoes-despesa/{despesa_id}/vinculo",
        {
          params: { path: { despesa_id: args.id } },
          body: { reajustar: false, ...args.vinculo },
        }
      )
      if (error || !data)
        throw new Error(mensagemErro(error, "falha ao vincular a transação"))
      return data
    },
    onSuccess: (_data, args) => {
      invalidar(qc)
      qc.invalidateQueries({ queryKey: divisoesKeys.detalhe(args.id) })
    },
  })
}

/** Saídas do usuário sem divisão perto da data — mesmo valor primeiro. */
export function useTransacoesCandidatas(
  valorCentavos: number,
  data: string,
  enabled = true
) {
  return useQuery({
    queryKey: ["divisoes", "candidatas", valorCentavos, data],
    enabled: enabled && valorCentavos > 0 && data !== "",
    queryFn: async (): Promise<Transacao[]> => {
      const { data: itens, error } = await api.GET(
        "/api/divisoes-despesa/transacoes-candidatas",
        { params: { query: { valor_centavos: valorCentavos, data } } }
      )
      if (error || !itens) throw new Error("falha ao buscar transações")
      return itens
    },
  })
}

export function useQuitarDivisao() {
  return useMarcarQuitada("quitar")
}

export function useReabrirDivisao() {
  return useMarcarQuitada("reabrir")
}
