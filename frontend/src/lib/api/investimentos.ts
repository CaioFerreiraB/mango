import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { api } from "@/lib/api/client"
import { mensagemErro } from "@/lib/api/erros"
import type { components } from "@/lib/api/schema"

export type Investimento = components["schemas"]["InvestimentoRead"]
export type InvestimentoTransacao = components["schemas"]["InvestimentoTransacaoRead"]
export type CarteiraResumo = components["schemas"]["CarteiraResumo"]
export type CarteiraAtivoRV = components["schemas"]["CarteiraAtivoRV"]
export type CarteiraAtivoRF = components["schemas"]["CarteiraAtivoRF"]
export type CarteiraItem = components["schemas"]["CarteiraItem"]
export type CarteiraPosicao = components["schemas"]["CarteiraPosicao"]
export type CarteiraGrupo = components["schemas"]["CarteiraGrupo"]
export type CarteiraSerie = components["schemas"]["CarteiraSerie"]
export type ProventosFII = components["schemas"]["ProventosFII"]
export type FundamentosFII = components["schemas"]["FundamentosFII"]
export type FundamentosFIIAlocacao = components["schemas"]["FundamentosFIIAlocacao"]
export type CotaSeriePonto = components["schemas"]["CotaSeriePonto"]
export type Ativo = components["schemas"]["AtivoRead"]
export type VisaoGeralInvestimentos = components["schemas"]["VisaoGeralInvestimentos"]
export type RecorteCarteira = "todos" | "renda_fixa" | "renda_variavel"

export const ativosKeys = { all: ["ativos"] as const }

export const investimentosKeys = {
  all: ["investimentos"] as const,
  resumo: ["investimentos", "resumo"] as const,
  visaoGeral: ["investimentos", "visao-geral"] as const,
  serie: (recorte: string, subtype: string | null, inicio: string, fim: string) =>
    ["investimentos", "serie", recorte, subtype, inicio, fim] as const,
  transacoes: (id: number) => ["investimentos", id, "transacoes"] as const,
  proventos: (id: number, inicio: string, fim: string) =>
    ["investimentos", id, "proventos", inicio, fim] as const,
  posicaoTransacoes: (ids: number[]) =>
    ["investimentos", "posicao", "transacoes", ids] as const,
  posicaoSerie: (ids: number[], inicio: string, fim: string) =>
    ["investimentos", "posicao", "serie", ids, inicio, fim] as const,
  posicaoProventos: (ids: number[], inicio: string, fim: string) =>
    ["investimentos", "posicao", "proventos", ids, inicio, fim] as const,
  posicaoFundamentos: (ids: number[]) =>
    ["investimentos", "posicao", "fundamentos", ids] as const,
  posicaoCotaSerie: (ids: number[], inicio: string, fim: string) =>
    ["investimentos", "posicao", "cota-serie", ids, inicio, fim] as const,
}

export function useInvestimentos() {
  return useQuery({
    queryKey: investimentosKeys.all,
    queryFn: async (): Promise<Investimento[]> => {
      const { data, error } = await api.GET("/api/investimentos")
      if (error || !data) throw new Error("falha ao carregar os investimentos")
      return data
    },
  })
}

export function useInvestimento(id: number | null) {
  return useQuery({
    queryKey: ["investimentos", id],
    enabled: id != null,
    queryFn: async (): Promise<Investimento> => {
      const { data, error } = await api.GET("/api/investimentos/{investimento_id}", {
        params: { path: { investimento_id: id! } },
      })
      if (error || !data) throw new Error("falha ao carregar o investimento")
      return data
    },
  })
}

/** Métricas do dashboard que não vêm do /resumo: rentabilidade 12m, dividendos, eventos, classe. */
export function useVisaoGeral() {
  return useQuery({
    queryKey: investimentosKeys.visaoGeral,
    queryFn: async (): Promise<VisaoGeralInvestimentos> => {
      const { data, error } = await api.GET("/api/investimentos/visao-geral")
      if (error || !data) throw new Error("falha ao carregar a visão geral")
      return data
    },
  })
}

/** Agregados prontos do servidor (totais, alocação, por ativo/tipo) — o client só exibe. */
export function useCarteiraResumo() {
  return useQuery({
    queryKey: investimentosKeys.resumo,
    queryFn: async (): Promise<CarteiraResumo> => {
      const { data, error } = await api.GET("/api/investimentos/resumo")
      if (error || !data) throw new Error("falha ao carregar a carteira")
      return data
    },
  })
}

/** Série da carteira (% acumulado TWR) no período, por recorte (§4.9). */
export function useCarteiraSerie(params: {
  recorte: RecorteCarteira
  subtype?: string | null
  inicio: string
  fim: string
}) {
  const { recorte, subtype, inicio, fim } = params
  return useQuery({
    queryKey: investimentosKeys.serie(recorte, subtype ?? null, inicio, fim),
    queryFn: async (): Promise<CarteiraSerie> => {
      const { data, error } = await api.GET("/api/investimentos/serie", {
        params: { query: { recorte, subtype: subtype ?? undefined, inicio, fim } },
      })
      if (error || !data) throw new Error("falha ao carregar a série da carteira")
      return data
    },
  })
}

/** Movimentos do investimento (aplicações, resgates, proventos). */
export function useInvestimentoTransacoes(id: number | null) {
  return useQuery({
    queryKey: investimentosKeys.transacoes(id ?? -1),
    enabled: id != null,
    queryFn: async (): Promise<InvestimentoTransacao[]> => {
      const { data, error } = await api.GET(
        "/api/investimentos/{investimento_id}/transacoes",
        { params: { path: { investimento_id: id! } } }
      )
      if (error || !data) throw new Error("falha ao carregar os movimentos")
      return data
    },
  })
}

/** Movimentos mesclados de um grupo de posições (drawer da Carteira). Vazio → hook desabilitado. */
export function usePosicaoTransacoes(ids: number[]) {
  return useQuery({
    queryKey: investimentosKeys.posicaoTransacoes(ids),
    enabled: ids.length > 0,
    queryFn: async (): Promise<InvestimentoTransacao[]> => {
      const { data, error } = await api.GET("/api/investimentos/posicao/transacoes", {
        params: { query: { ids } },
      })
      if (error || !data) throw new Error("falha ao carregar os movimentos")
      return data
    },
  })
}

/** Série (evolução da posição) de um grupo no período. */
export function usePosicaoSerie(
  ids: number[],
  periodo: { inicio: string; fim: string }
) {
  return useQuery({
    queryKey: investimentosKeys.posicaoSerie(ids, periodo.inicio, periodo.fim),
    enabled: ids.length > 0,
    queryFn: async (): Promise<CarteiraSerie> => {
      const { data, error } = await api.GET("/api/investimentos/posicao/serie", {
        params: { query: { ids, inicio: periodo.inicio, fim: periodo.fim } },
      })
      if (error || !data) throw new Error("falha ao carregar a série da posição")
      return data
    },
  })
}

/** Proventos + DY de um grupo no período (agregados no servidor). */
export function usePosicaoProventos(
  ids: number[],
  periodo: { inicio: string; fim: string }
) {
  return useQuery({
    queryKey: investimentosKeys.posicaoProventos(ids, periodo.inicio, periodo.fim),
    enabled: ids.length > 0,
    queryFn: async (): Promise<ProventosFII> => {
      const { data, error } = await api.GET("/api/investimentos/posicao/proventos", {
        params: { query: { ids, inicio: periodo.inicio, fim: periodo.fim } },
      })
      if (error || !data) throw new Error("falha ao carregar os proventos")
      return data
    },
  })
}

/** Fundamentos do FII da posição (CVM) + P/VP. `enabled` só p/ FIIs (subtype REAL_ESTATE_FUND). */
export function usePosicaoFundamentos(ids: number[], enabled: boolean) {
  return useQuery({
    queryKey: investimentosKeys.posicaoFundamentos(ids),
    enabled: enabled && ids.length > 0,
    queryFn: async (): Promise<FundamentosFII> => {
      const { data, error } = await api.GET("/api/investimentos/posicao/fundamentos", {
        params: { query: { ids } },
      })
      if (error || !data) throw new Error("falha ao carregar os fundamentos")
      return data
    },
  })
}

/** Evolução do preço da cota do FII (brapi) no período. Vazio sem token/preço — o gráfico some. */
export function usePosicaoCotaSerie(
  ids: number[],
  periodo: { inicio: string; fim: string },
  enabled: boolean
) {
  return useQuery({
    queryKey: investimentosKeys.posicaoCotaSerie(ids, periodo.inicio, periodo.fim),
    enabled: enabled && ids.length > 0,
    queryFn: async (): Promise<CotaSeriePonto[]> => {
      const { data, error } = await api.GET("/api/investimentos/posicao/cota-serie", {
        params: { query: { ids, inicio: periodo.inicio, fim: periodo.fim } },
      })
      if (error || !data) throw new Error("falha ao carregar a série da cota")
      return data
    },
  })
}

/** Ativos do usuário (agrupamento de compras de renda fixa) — p/ o seletor de vínculo. */
export function useAtivos() {
  return useQuery({
    queryKey: ativosKeys.all,
    queryFn: async (): Promise<Ativo[]> => {
      const { data, error } = await api.GET("/api/ativos")
      if (error || !data) throw new Error("falha ao carregar os ativos")
      return data
    },
  })
}

export function useCriarAtivo() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (nome: string): Promise<Ativo> => {
      const { data, error } = await api.POST("/api/ativos", { body: { nome } })
      if (error || !data) throw new Error(mensagemErro(error, "falha ao criar o ativo"))
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ativosKeys.all }),
    onError: (e) => toast.error(e.message),
  })
}

export function useRenomearAtivo() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (args: { id: number; nome: string }): Promise<Ativo> => {
      const { data, error } = await api.PATCH("/api/ativos/{item_id}", {
        params: { path: { item_id: args.id } },
        body: { nome: args.nome },
      })
      if (error || !data) throw new Error(mensagemErro(error, "falha ao renomear o ativo"))
      return data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ativosKeys.all })
      qc.invalidateQueries({ queryKey: investimentosKeys.resumo })
      toast.success("Ativo renomeado.")
    },
    onError: (e) => toast.error(e.message),
  })
}

/** Vincula uma compra (posição) a um ativo — `ativoId=null` desvincula (vira avulsa). */
export function useVincularAtivo() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (args: {
      investimentoId: number
      ativoId: number | null
    }): Promise<Investimento> => {
      const { data, error } = await api.PATCH("/api/investimentos/{investimento_id}", {
        params: { path: { investimento_id: args.investimentoId } },
        body: { ativo_id: args.ativoId },
      })
      if (error || !data) throw new Error(mensagemErro(error, "falha ao vincular ao ativo"))
      return data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: investimentosKeys.resumo })
      qc.invalidateQueries({ queryKey: ativosKeys.all })
      toast.success("Compra vinculada ao ativo.")
    },
    onError: (e) => toast.error(e.message),
  })
}

export type AporteManualCreate = components["schemas"]["AporteManualCreate"]

/** Invalida tudo que depende dos movimentos de uma posição (resumo, visão geral e a lista). */
function invalidarAportes(qc: ReturnType<typeof useQueryClient>, ids: number[]) {
  qc.invalidateQueries({ queryKey: investimentosKeys.resumo })
  qc.invalidateQueries({ queryKey: investimentosKeys.visaoGeral })
  qc.invalidateQueries({ queryKey: investimentosKeys.posicaoTransacoes(ids) })
}

/** Adiciona um aporte (compra) à mão a uma posição — entra no custo médio (§4.9). */
export function useCriarAporte(ids: number[]) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (args: {
      investimentoId: number
      corpo: AporteManualCreate
    }): Promise<InvestimentoTransacao> => {
      const { data, error } = await api.POST("/api/investimentos/{investimento_id}/aportes", {
        params: { path: { investimento_id: args.investimentoId } },
        body: args.corpo,
      })
      if (error || !data) throw new Error(mensagemErro(error, "falha ao adicionar o aporte"))
      return data
    },
    onSuccess: () => {
      invalidarAportes(qc, ids)
      toast.success("Aporte adicionado.")
    },
    onError: (e) => toast.error(e.message),
  })
}

/** Edita um aporte manual (data/quantidade/valor). */
export function useEditarAporte(ids: number[]) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (args: {
      aporteId: number
      corpo: Partial<AporteManualCreate>
    }): Promise<InvestimentoTransacao> => {
      const { data, error } = await api.PATCH("/api/investimentos/aportes/{aporte_id}", {
        params: { path: { aporte_id: args.aporteId } },
        body: args.corpo,
      })
      if (error || !data) throw new Error(mensagemErro(error, "falha ao salvar o aporte"))
      return data
    },
    onSuccess: () => {
      invalidarAportes(qc, ids)
      toast.success("Aporte atualizado.")
    },
    onError: (e) => toast.error(e.message),
  })
}

/** Exclui um aporte manual. */
export function useExcluirAporte(ids: number[]) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (aporteId: number): Promise<void> => {
      const { error } = await api.DELETE("/api/investimentos/aportes/{aporte_id}", {
        params: { path: { aporte_id: aporteId } },
      })
      if (error) throw new Error(mensagemErro(error, "falha ao excluir o aporte"))
    },
    onSuccess: () => {
      invalidarAportes(qc, ids)
      toast.success("Aporte removido.")
    },
    onError: (e) => toast.error(e.message),
  })
}

/** Proventos + dividend yield do período, calculados no servidor (§4.9 FII). */
export function useProventosFII(
  id: number | null,
  periodo: { inicio: string; fim: string }
) {
  return useQuery({
    queryKey: investimentosKeys.proventos(id ?? -1, periodo.inicio, periodo.fim),
    enabled: id != null,
    queryFn: async (): Promise<ProventosFII> => {
      const { data, error } = await api.GET(
        "/api/investimentos/{investimento_id}/proventos",
        {
          params: {
            path: { investimento_id: id! },
            query: { inicio: periodo.inicio, fim: periodo.fim },
          },
        }
      )
      if (error || !data) throw new Error("falha ao carregar os proventos")
      return data
    },
  })
}
