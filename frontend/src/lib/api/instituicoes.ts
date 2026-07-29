import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { api } from "@/lib/api/client"
import { contasKeys, type Conta } from "@/lib/api/contas"
import { mensagemErro } from "@/lib/api/erros"
import type { components } from "@/lib/api/schema"

export type Instituicao = components["schemas"]["InstituicaoRead"]
export type Connector = components["schemas"]["ConnectorRead"]

const instituicoesKey = ["instituicoes"] as const

export function useInstituicoes() {
  return useQuery({
    queryKey: instituicoesKey,
    queryFn: async (): Promise<Instituicao[]> => {
      const { data, error } = await api.GET("/api/instituicoes")
      if (error || !data) throw new Error("falha ao carregar instituições")
      return data
    },
  })
}

/** Catálogo do Pluggy p/ o seletor de vínculo manual. `enabled` evita buscar antes de abrir. */
export function useConnectoresPluggy(enabled = true) {
  return useQuery({
    queryKey: ["pluggy-connectores"],
    enabled,
    staleTime: 10 * 60_000, // o catálogo muda raramente
    queryFn: async (): Promise<Connector[]> => {
      const { data, error } = await api.GET("/api/pluggy/connectores")
      if (error || !data)
        throw new Error("falha ao carregar instituições do Pluggy")
      return data
    },
  })
}

/** Vincula (ou remove, com `connector=null`) a instituição manual de uma conta. */
export function useVincularInstituicao() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (args: {
      contaId: number
      connector: Connector | null
    }): Promise<Conta> => {
      const { data, error } = await api.PUT(
        "/api/contas/{conta_id}/instituicao",
        {
          params: { path: { conta_id: args.contaId } },
          body: args.connector
            ? {
                pluggy_connector_id: args.connector.pluggy_connector_id,
                nome: args.connector.nome,
                logo_url: args.connector.logo_url,
              }
            : { pluggy_connector_id: null },
        }
      )
      if (error || !data)
        throw new Error(mensagemErro(error, "falha ao vincular a instituição"))
      return data
    },
    onSuccess: (_data, args) => {
      qc.invalidateQueries({ queryKey: contasKeys.all })
      qc.invalidateQueries({ queryKey: contasKeys.detalhe(args.contaId) })
      qc.invalidateQueries({ queryKey: instituicoesKey })
      toast.success(
        args.connector ? "Instituição vinculada." : "Vínculo removido."
      )
    },
    onError: (e) => toast.error(e.message),
  })
}

/** Instituição efetiva de uma conta: a manual (se houver) sobrepõe a original do sync. */
export function instituicaoEfetiva(
  conta: Pick<Conta, "instituicao_id" | "instituicao_manual_id">,
  porId: Map<number, Instituicao>
): Instituicao | undefined {
  return (
    (conta.instituicao_manual_id != null
      ? porId.get(conta.instituicao_manual_id)
      : undefined) ?? porId.get(conta.instituicao_id)
  )
}
