import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { api } from "@/lib/api/client"
import { contasKeys } from "@/lib/api/contas"
import { mensagemErro } from "@/lib/api/erros"
import type { Connector } from "@/lib/api/instituicoes"
import type { components } from "@/lib/api/schema"

export type Credencial = components["schemas"]["CredencialPluggyRead"]
export type Item = components["schemas"]["ItemPluggyRead"]
export type ResumoSync = components["schemas"]["ResumoSyncRead"]

export const conexoesKeys = {
  credenciais: ["credenciais-pluggy"] as const,
  itens: ["itens-pluggy"] as const,
}

/** Revalida tudo que o sync pode ter mudado. */
function invalidarDados(qc: ReturnType<typeof useQueryClient>) {
  for (const k of [
    ["itens-pluggy"],
    ["contas"],
    ["transacoes"],
    ["faturas"],
    ["dashboard"],
    ["investimentos"],
  ]) {
    qc.invalidateQueries({ queryKey: k })
  }
}

export function useCredenciais() {
  return useQuery({
    queryKey: conexoesKeys.credenciais,
    queryFn: async (): Promise<Credencial[]> => {
      const { data, error } = await api.GET("/api/credenciais-pluggy")
      if (error || !data) throw new Error("falha ao carregar credenciais")
      return data
    },
  })
}

export function useItens() {
  return useQuery({
    queryKey: conexoesKeys.itens,
    queryFn: async (): Promise<Item[]> => {
      const { data, error } = await api.GET("/api/itens-pluggy")
      if (error || !data) throw new Error("falha ao carregar conexões")
      return data
    },
  })
}

export function useCriarCredencial() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: { client_id: string; client_secret: string }) => {
      const { data, error } = await api.POST("/api/credenciais-pluggy", {
        body,
      })
      if (error || !data)
        throw new Error(mensagemErro(error, "falha ao salvar credencial"))
      return data
    },
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: conexoesKeys.credenciais }),
  })
}

/** Testa a credencial guardada contra o Pluggy — devolve só o booleano (S1). */
export function useTestarCredencial() {
  return useMutation({
    mutationFn: async (): Promise<boolean> => {
      const { data, error } = await api.POST(
        "/api/credenciais-pluggy/testar",
        {}
      )
      if (error || !data) throw new Error("falha ao testar credencial")
      return data.valida
    },
  })
}

export function useCriarItem() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: {
      credencial_id: number
      pluggy_item_id: string
    }) => {
      const { data, error } = await api.POST("/api/itens-pluggy", { body })
      if (error || !data)
        throw new Error(mensagemErro(error, "falha ao adicionar conexão"))
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: conexoesKeys.itens }),
  })
}

/** Vincula (ou remove, com `connector=null`) a instituição manual de uma conexão — vale para
 * todas as contas do item. */
export function useVincularInstituicaoItem() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (args: { itemId: number; connector: Connector | null }): Promise<Item> => {
      const { data, error } = await api.PUT("/api/itens-pluggy/{item_id}/instituicao", {
        params: { path: { item_id: args.itemId } },
        body: args.connector
          ? {
              pluggy_connector_id: args.connector.pluggy_connector_id,
              nome: args.connector.nome,
              logo_url: args.connector.logo_url,
            }
          : { pluggy_connector_id: null },
      })
      if (error || !data)
        throw new Error(mensagemErro(error, "falha ao vincular a instituição"))
      return data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: conexoesKeys.itens })
      qc.invalidateQueries({ queryKey: contasKeys.all })
    },
    onError: (e) => toast.error(e.message),
  })
}

export function useRemoverItem() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (itemId: number) => {
      const { error } = await api.DELETE("/api/itens-pluggy/{item_id}", {
        params: { path: { item_id: itemId } },
      })
      if (error) throw new Error("falha ao remover conexão")
    },
    onSuccess: () => invalidarDados(qc),
  })
}

function toastResumo(r: ResumoSync) {
  toast.success(
    `Sincronizado: ${r.contas} conta(s), ${r.transacoes_novas} nova(s) transação(ões)`
  )
}

export function useSincronizarTudo() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (): Promise<ResumoSync> => {
      const { data, error } = await api.POST("/api/sync", {})
      if (error || !data)
        throw new Error(mensagemErro(error, "falha ao sincronizar"))
      return data
    },
    onSuccess: (r) => {
      invalidarDados(qc)
      toastResumo(r)
    },
    onError: (e) => toast.error(e.message),
  })
}

export function useSincronizarItem() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (itemId: number): Promise<ResumoSync> => {
      const { data, error } = await api.POST(
        "/api/itens-pluggy/{item_id}/sincronizar",
        {
          params: { path: { item_id: itemId } },
        }
      )
      if (error || !data)
        throw new Error(mensagemErro(error, "falha ao sincronizar"))
      return data
    },
    onSuccess: (r) => {
      invalidarDados(qc)
      toastResumo(r)
    },
    onError: (e) => toast.error(e.message),
  })
}
