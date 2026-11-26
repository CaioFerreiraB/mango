import { useMemo } from "react"
import { useQuery } from "@tanstack/react-query"

import { api } from "@/lib/api/client"
import type { components } from "@/lib/api/schema"

export type Conta = components["schemas"]["ContaRead"]
export type ContaDetalhe = components["schemas"]["ContaDetalheRead"]
export type SaldoDiarioPonto = components["schemas"]["SaldoDiarioPonto"]
export type FaturaResumoBucket = components["schemas"]["FaturaResumoBucket"]

export const contasKeys = {
  all: ["contas"] as const,
  detalhe: (id: number) => ["contas", id] as const,
  saldosDiarios: ["contas", "saldos-diarios"] as const,
  faturasResumo: (id: number) => ["contas", id, "faturas-resumo"] as const,
}

export function useContas() {
  return useQuery({
    queryKey: contasKeys.all,
    queryFn: async (): Promise<Conta[]> => {
      const { data, error } = await api.GET("/api/contas")
      if (error || !data) throw new Error("falha ao carregar contas")
      return data
    },
  })
}

/** Série de saldo diário (fecho de cada dia) por conta BANK — sparkline dos cards. Mapa por id. */
export function useContasSaldosDiarios(dias = 30) {
  return useQuery({
    queryKey: [...contasKeys.saldosDiarios, dias],
    queryFn: async (): Promise<Map<number, SaldoDiarioPonto[]>> => {
      const { data, error } = await api.GET("/api/contas/saldos-diarios", {
        params: { query: { dias } },
      })
      if (error || !data) throw new Error("falha ao carregar saldos diários")
      return new Map(data.map((s) => [s.conta_id, s.pontos]))
    },
  })
}

/** Últimas faturas do cartão (cronológico) com total + quebra por categoria — gráfico do detalhe. */
export function useFaturasResumo(contaId: number, limite = 6) {
  return useQuery({
    queryKey: [...contasKeys.faturasResumo(contaId), limite],
    queryFn: async (): Promise<FaturaResumoBucket[]> => {
      const { data, error } = await api.GET(
        "/api/contas/{conta_id}/faturas-resumo",
        {
          params: { path: { conta_id: contaId }, query: { limite } },
        }
      )
      if (error || !data) throw new Error("falha ao carregar faturas do cartão")
      return data.buckets
    },
  })
}

export function useConta(contaId: number) {
  return useQuery({
    queryKey: contasKeys.detalhe(contaId),
    queryFn: async (): Promise<ContaDetalhe> => {
      const { data, error } = await api.GET("/api/contas/{conta_id}", {
        params: { path: { conta_id: contaId } },
      })
      if (error || !data) throw new Error("falha ao carregar a conta")
      return data
    },
    // Id ainda desconhecido (ex.: fatura carregando) → não pergunta pela conta 0.
    enabled: contaId > 0,
  })
}

/** Saldo somado das contas correntes/poupança (BANK) por dia, em ordem cronológica — a curva do
 *  herói de saldo (Início e Dashboard). */
export function useSaldoContasSerie(dias = 30) {
  const contas = useContas()
  const saldos = useContasSaldosDiarios(dias)
  return useMemo(() => {
    const bancos = new Set(
      (contas.data ?? []).filter((c) => c.type === "BANK").map((c) => c.id)
    )
    const porDia = new Map<string, number>()
    for (const [id, pontos] of saldos.data ?? []) {
      if (!bancos.has(id)) continue
      for (const p of pontos)
        porDia.set(p.data, (porDia.get(p.data) ?? 0) + p.saldo_centavos)
    }
    // Data ISO ordena cronologicamente.
    return [...porDia]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([data, saldo_centavos]) => ({ data, saldo_centavos }))
  }, [contas.data, saldos.data])
}
