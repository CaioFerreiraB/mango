import { useQuery } from "@tanstack/react-query"

import { api } from "@/lib/api/client"
import type { Conta } from "@/lib/api/contas"
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

/** Mesmo catálogo, pelo gêmeo público do wizard (no setup ainda não há sessão para o endpoint
 *  protegido). Some com 409 assim que a instância é configurada — daí só o hook acima vale. */
export function useConnectoresSetup(enabled = true) {
  return useQuery({
    queryKey: ["setup-connectores"],
    enabled,
    staleTime: 10 * 60_000,
    queryFn: async (): Promise<Connector[]> => {
      const { data, error } = await api.GET("/api/setup/connectores")
      if (error || !data)
        throw new Error("falha ao carregar instituições do Pluggy")
      return data
    },
  })
}

/** Instituição efetiva de uma conta: a manual (se houver) sobrepõe a original do sync.
 *
 * O vínculo manual é da CONEXÃO (ver `useVincularInstituicaoItem` em `lib/api/conexoes.ts`), mas
 * continua chegando aqui em `conta.instituicao_manual_id` — o backend computa a partir do item. */
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
