import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { api } from "@/lib/api/client"
import { mensagemErro } from "@/lib/api/erros"
import type { components } from "@/lib/api/schema"

export type ConfiguracaoSistema = components["schemas"]["ConfiguracaoSistemaRead"]

export const configuracaoSistemaKeys = {
  detalhe: ["configuracao-sistema"] as const,
}

/** Config global da instância (§4.11-otimização) — leitura aberta a qualquer autenticado. */
export function useConfiguracaoSistema() {
  return useQuery({
    queryKey: configuracaoSistemaKeys.detalhe,
    queryFn: async (): Promise<ConfiguracaoSistema> => {
      const { data, error } = await api.GET("/api/configuracao-sistema")
      if (error || !data) throw new Error(mensagemErro(error, "falha ao carregar a configuração"))
      return data
    },
  })
}

/** Escrita restrita ao dono da instância (`require_admin` no backend). */
export function useAtualizarConfiguracaoSistema() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (otimizarTransacoesDivisao: boolean): Promise<ConfiguracaoSistema> => {
      const { data, error } = await api.PATCH("/api/configuracao-sistema", {
        body: { otimizar_transacoes_divisao: otimizarTransacoesDivisao },
      })
      if (error || !data)
        throw new Error(mensagemErro(error, "falha ao atualizar a configuração"))
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: configuracaoSistemaKeys.detalhe }),
  })
}
