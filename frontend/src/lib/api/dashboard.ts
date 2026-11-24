import { useQuery } from "@tanstack/react-query"

import { api } from "@/lib/api/client"
import type { components } from "@/lib/api/schema"

export type DashboardResumo = components["schemas"]["DashboardResumo"]
export type GastoCategoria = components["schemas"]["GastoCategoria"]
export type DashboardSeries = components["schemas"]["DashboardSeries"]
export type SerieBucket = components["schemas"]["SerieBucket"]
export type Granularidade = "diaria" | "semanal" | "mensal" | "anual"
/** Competência: compra no cartão conta na data da compra, sem o pagamento da fatura. Caixa: só o
 *  que saiu/entrou na conta — pagamento da fatura no lugar das compras do cartão. */
export type Visao = "competencia" | "caixa"

/** "Por {rótulo}" nas descrições dos gráficos. */
export const PERIODO_LABEL: Record<Granularidade, string> = {
  diaria: "dia",
  semanal: "semana",
  mensal: "mês",
  anual: "ano",
}

/** Agregados do período (§4.10). Sem `inicio/fim` o backend usa o mês corrente (fuso SP). */
export function useDashboard(
  periodo?: { inicio?: string; fim?: string },
  visao: Visao = "competencia"
) {
  return useQuery({
    queryKey: [
      "dashboard",
      periodo?.inicio ?? null,
      periodo?.fim ?? null,
      visao,
    ],
    queryFn: async (): Promise<DashboardResumo> => {
      const { data, error } = await api.GET("/api/dashboard", {
        params: {
          query: { inicio: periodo?.inicio, fim: periodo?.fim, visao },
        },
      })
      if (error || !data) throw new Error("falha ao carregar o dashboard")
      return data
    },
  })
}

/** Série temporal (semanal/mensal) de entradas/saídas/resultado e gasto por categoria. */
export function useDashboardSeries(
  periodo: { inicio?: string; fim?: string } | undefined,
  granularidade: Granularidade,
  visao: Visao = "competencia"
) {
  return useQuery({
    queryKey: [
      "dashboard",
      "series",
      periodo?.inicio ?? null,
      periodo?.fim ?? null,
      granularidade,
      visao,
    ],
    queryFn: async (): Promise<DashboardSeries> => {
      const { data, error } = await api.GET("/api/dashboard/series", {
        params: {
          query: {
            inicio: periodo?.inicio,
            fim: periodo?.fim,
            granularidade,
            visao,
          },
        },
      })
      if (error || !data)
        throw new Error("falha ao carregar a série do dashboard")
      return data
    },
  })
}

export type PatrimonioPonto = components["schemas"]["PatrimonioPonto"]

/** Evolução patrimonial mês a mês (contas BANK + investimentos), terminando no mês corrente. */
export function usePatrimonio(meses = 12) {
  return useQuery({
    queryKey: ["dashboard", "patrimonio", meses],
    queryFn: async (): Promise<PatrimonioPonto[]> => {
      const { data, error } = await api.GET("/api/dashboard/patrimonio", {
        params: { query: { meses } },
      })
      if (error || !data) throw new Error("falha ao carregar o patrimônio")
      return data.pontos
    },
  })
}

export type CartoesResumo = components["schemas"]["CartoesResumo"]

/** Painel dos cartões: compras do mês, fatura atual, próximas, limite e resumo do ano. */
export function useCartoesPainel() {
  return useQuery({
    queryKey: ["dashboard", "cartoes"],
    queryFn: async (): Promise<CartoesResumo> => {
      const { data, error } = await api.GET("/api/dashboard/cartoes")
      if (error || !data) throw new Error("falha ao carregar os cartões")
      return data
    },
  })
}

export type AnaliseNatureza = components["schemas"]["AnaliseNatureza"]
export type Natureza = "receita" | "despesa"

/** Aba Receitas ou Despesas: totais, categorias, contrapartes, meios, dia da semana, acumulado e
 *  orçamento × realizado — tudo do mesmo recorte dos KPIs. */
export function useAnalise(
  natureza: Natureza,
  periodo: { inicio: string; fim: string },
  visao: Visao = "competencia"
) {
  return useQuery({
    queryKey: [
      "dashboard",
      "analise",
      natureza,
      periodo.inicio,
      periodo.fim,
      visao,
    ],
    queryFn: async (): Promise<AnaliseNatureza> => {
      const { data, error } = await api.GET("/api/dashboard/analise", {
        params: { query: { natureza, ...periodo, visao } },
      })
      if (error || !data) throw new Error("falha ao carregar a análise")
      return data
    },
  })
}

/** Pedaço da análise aberto num gráfico (categoria, contraparte, meio e/ou conta). */
export type FiltroAnalise = {
  natureza: Natureza
  titulo: string
  categoria_id?: string
  contraparte?: string
  meio?: string
  conta_id?: number
}

/** Transações de um pedaço da análise — mesmo recorte do servidor, a soma bate com o gráfico. */
export function useTransacoesDaAnalise(
  filtro: FiltroAnalise | null,
  periodo: { inicio: string; fim: string },
  visao: Visao = "competencia"
) {
  return useQuery({
    queryKey: [
      "dashboard",
      "analise-transacoes",
      filtro,
      periodo.inicio,
      periodo.fim,
      visao,
    ],
    enabled: filtro !== null,
    queryFn: async () => {
      const { natureza, categoria_id, contraparte, meio, conta_id } = filtro!
      const { data, error } = await api.GET(
        "/api/dashboard/analise/transacoes",
        {
          params: {
            query: {
              natureza,
              categoria_id,
              contraparte,
              meio,
              conta_id,
              ...periodo,
              visao,
            },
          },
        }
      )
      if (error || !data) throw new Error("falha ao carregar as transações")
      return data
    },
  })
}
