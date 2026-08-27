import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { api } from "@/lib/api/client"
import { mensagemErro } from "@/lib/api/erros"
import type { components } from "@/lib/api/schema"

export type RegraCategorizacao = components["schemas"]["RegraCategorizacaoRead"]
export type RegraCategorizacaoCreate =
  components["schemas"]["RegraCategorizacaoCreate"]
export type TipoMatch = RegraCategorizacaoCreate["tipo_match"]

/** Espelha `MAX_REGRAS` do backend — usado só para o contador da UI; quem impõe é o servidor. */
export const MAX_REGRAS = 200

export const regrasKeys = {
  all: ["regras-categorizacao"] as const,
}

export const ROTULO_TIPO_MATCH: Record<TipoMatch, string> = {
  exato: "Texto exato",
  contem: "Contém o texto",
}

/** Regras que mapeiam o nome de uma transação para uma categoria (§4.5). */
export function useRegrasCategorizacao() {
  return useQuery({
    queryKey: regrasKeys.all,
    queryFn: async (): Promise<RegraCategorizacao[]> => {
      const { data, error } = await api.GET("/api/regras-categorizacao")
      if (error || !data)
        throw new Error(mensagemErro(error, "falha ao carregar as regras"))
      return data
    },
  })
}

/** Criar/editar/apagar regra recategoriza o histórico no servidor — tudo que deriva de categoria
 *  precisa ser reconsultado. */
function invalidar(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: regrasKeys.all })
  qc.invalidateQueries({ queryKey: ["transacoes"] })
  qc.invalidateQueries({ queryKey: ["dashboard"] })
  qc.invalidateQueries({ queryKey: ["dashboard-series"] })
  qc.invalidateQueries({ queryKey: ["orcamentos"] })
}

export function useCriarRegra() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (
      body: RegraCategorizacaoCreate
    ): Promise<RegraCategorizacao> => {
      const { data, error } = await api.POST("/api/regras-categorizacao", {
        body,
      })
      if (error || !data)
        throw new Error(mensagemErro(error, "falha ao criar a regra"))
      return data
    },
    onSuccess: () => invalidar(qc),
  })
}

export function useAtualizarRegra() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({
      id,
      patch,
    }: {
      id: number
      patch: Partial<RegraCategorizacaoCreate>
    }): Promise<RegraCategorizacao> => {
      const { data, error } = await api.PATCH(
        "/api/regras-categorizacao/{regra_id}",
        {
          params: { path: { regra_id: id } },
          body: patch,
        }
      )
      if (error || !data)
        throw new Error(mensagemErro(error, "falha ao atualizar a regra"))
      return data
    },
    onSuccess: () => invalidar(qc),
  })
}

export function useRemoverRegra() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: number): Promise<void> => {
      const { error } = await api.DELETE(
        "/api/regras-categorizacao/{regra_id}",
        {
          params: { path: { regra_id: id } },
        }
      )
      if (error)
        throw new Error(mensagemErro(error, "falha ao excluir a regra"))
    },
    onSuccess: () => invalidar(qc),
  })
}
