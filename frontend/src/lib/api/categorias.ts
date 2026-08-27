import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useMemo } from "react"

import { api } from "@/lib/api/client"
import { mensagemErro } from "@/lib/api/erros"
import type { components } from "@/lib/api/schema"

export type Categoria = components["schemas"]["CategoriaRead"]
/** Nomes de ícone que o backend aceita — vem do OpenAPI, então a lista não é mantida duas vezes. */
export type IconeCategoria = NonNullable<Categoria["icone"]>

export const categoriasKeys = {
  all: ["categorias"] as const,
}

/** Taxonomia do Pluggy + categorias criadas pelo usuário (§4.5).
 *
 * Já foi cacheada com `staleTime: Infinity` ("fixa → para sempre"), o que deixou de valer quando a
 * taxonomia virou editável: criar, renomear, ativar e desativar mudam esta lista. Fica no
 * `staleTime` padrão e as mutações invalidam a chave.
 *
 * Devolve TUDO, inclusive as inativas (que vêm com `ativa: false`) — o rótulo de uma categoria
 * ainda referenciada por um ajuste manual precisa continuar resolvendo. Quem oferece escolha ao
 * usuário é que filtra (ver `CategoriaSelect`).
 */
export function useCategorias() {
  return useQuery({
    queryKey: categoriasKeys.all,
    queryFn: async (): Promise<Categoria[]> => {
      const { data, error } = await api.GET("/api/categorias")
      if (error || !data)
        throw new Error(mensagemErro(error, "falha ao carregar categorias"))
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
  // `useMemo`: sem ele o Map é recriado a cada render e quebra a memoização de quem o recebe.
  return useMemo(
    () => new Map((data ?? []).map((c) => [c.pluggy_id, nomeCategoria(c)])),
    [data]
  )
}

/** Mudar a taxonomia muda a categoria efetiva das transações — logo, dashboard e orçamentos. */
function invalidar(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: categoriasKeys.all })
  qc.invalidateQueries({ queryKey: ["transacoes"] })
  qc.invalidateQueries({ queryKey: ["dashboard"] })
  qc.invalidateQueries({ queryKey: ["dashboard-series"] })
  qc.invalidateQueries({ queryKey: ["orcamentos"] })
}

export function useCriarCategoria() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: {
      nome: string
      icone?: IconeCategoria | null
    }): Promise<Categoria> => {
      const { data, error } = await api.POST("/api/categorias", { body })
      if (error || !data)
        throw new Error(mensagemErro(error, "falha ao criar categoria"))
      return data
    },
    onSuccess: () => invalidar(qc),
  })
}

export function useAtualizarCategoria() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({
      id,
      patch,
    }: {
      id: string
      patch: { nome?: string; icone?: IconeCategoria | null; ativa?: boolean }
    }): Promise<Categoria> => {
      const { data, error } = await api.PATCH("/api/categorias/{pluggy_id}", {
        params: { path: { pluggy_id: id } },
        body: patch,
      })
      if (error || !data)
        throw new Error(mensagemErro(error, "falha ao atualizar categoria"))
      return data
    },
    onSuccess: () => invalidar(qc),
  })
}

export function useRemoverCategoria() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string): Promise<void> => {
      const { error } = await api.DELETE("/api/categorias/{pluggy_id}", {
        params: { path: { pluggy_id: id } },
      })
      // O backend recusa com 409 quando a categoria está em uso em orçamentos — a mensagem dele
      // diz em quantos, então repassá-la é melhor que um texto genérico.
      if (error)
        throw new Error(mensagemErro(error, "falha ao excluir categoria"))
    },
    onSuccess: () => invalidar(qc),
  })
}
