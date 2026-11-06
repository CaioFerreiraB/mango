import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { api } from "@/lib/api/client"
import type { components } from "@/lib/api/schema"
import type { Transacao } from "@/lib/api/transacoes"

export type Orcamento = components["schemas"]["OrcamentoRead"]
export type OrcamentoCreate = components["schemas"]["OrcamentoCreate"]
export type OrcamentoUpdate = components["schemas"]["OrcamentoUpdate"]
export type OrcamentoMensal = components["schemas"]["OrcamentoMensalRead"]
export type OrcamentoMensalCreate =
  components["schemas"]["OrcamentoMensalCreate"]
export type OrcamentoConsumo = components["schemas"]["OrcamentoConsumoRead"]
export type OrcamentoConsumoItem = components["schemas"]["OrcamentoConsumoItem"]

export const orcamentosKeys = {
  all: ["orcamentos"] as const,
  consumo: (ano: number, mes: number) =>
    ["orcamentos", "consumo", ano, mes] as const,
}

/** Consumo e alertas (50/75/90/100%) dos orçamentos do mês (§4.6). */
export function useConsumoOrcamentos(ano: number, mes: number) {
  return useQuery({
    queryKey: orcamentosKeys.consumo(ano, mes),
    queryFn: async (): Promise<OrcamentoConsumo> => {
      const { data, error } = await api.GET("/api/orcamentos/consumo", {
        params: { query: { ano, mes } },
      })
      if (error || !data)
        throw new Error("falha ao carregar o consumo dos orçamentos")
      return data
    },
  })
}

/** Linha da Visão Geral cujas transações o usuário abriu: uma categoria orçada ou o
 *  "Não planejado" (`categoriaId: null`) daquele tipo. */
export type AlvoDrilldown = {
  tipo: "despesa" | "receita"
  categoriaId: string | null
}

/** Transações que compõem uma linha do consumo do mês — mesmo recorte do servidor, então somam
 *  o realizado exibido. Chave sob `orcamentos` → invalidada junto com o consumo (inclusive ao
 *  recategorizar uma transação no drawer). */
export function useTransacoesDoOrcamento(
  ano: number,
  mes: number,
  alvo: AlvoDrilldown | null
) {
  return useQuery({
    queryKey: ["orcamentos", "consumo", ano, mes, "transacoes", alvo],
    enabled: alvo !== null,
    queryFn: async (): Promise<Transacao[]> => {
      const { tipo, categoriaId } = alvo!
      const { data, error } = await api.GET(
        "/api/orcamentos/consumo/transacoes",
        {
          params: {
            query:
              categoriaId === null
                ? { ano, mes, tipo, nao_planejado: true }
                : { ano, mes, tipo, categoria_id: categoriaId },
          },
        }
      )
      if (error || !data) throw new Error("falha ao carregar as transações")
      return data.items
    },
  })
}

function invalidar(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: orcamentosKeys.all })
  qc.invalidateQueries({ queryKey: ["dashboard"] })
}

/** Orçamentos padrão (recorrentes) do usuário, um por categoria configurada. */
export function useOrcamentos() {
  return useQuery({
    queryKey: orcamentosKeys.all,
    queryFn: async (): Promise<Orcamento[]> => {
      const { data, error } = await api.GET("/api/orcamentos")
      if (error || !data) throw new Error("falha ao carregar os orçamentos")
      return data
    },
  })
}

export function useCriarOrcamento() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: OrcamentoCreate): Promise<Orcamento> => {
      const { data, error } = await api.POST("/api/orcamentos", { body })
      if (error || !data) throw new Error("falha ao criar o orçamento")
      return data
    },
    onSuccess: () => invalidar(qc),
  })
}

/** Edita o limite **padrão** (recorrente) e/ou a `ordem` do orçamento — nunca a linha de um
 *  mês específico. Só manda ao servidor os campos presentes (PATCH é `exclude_unset`). */
export function useAtualizarOrcamentoPadrao() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (args: {
      id: number
      limite_padrao_centavos?: number
      ordem?: number
      notificar?: boolean
    }): Promise<Orcamento> => {
      const { id, ...body } = args
      const { data, error } = await api.PATCH(
        "/api/orcamentos/{orcamento_id}",
        {
          params: { path: { orcamento_id: id } },
          body,
        }
      )
      if (error || !data) throw new Error("falha ao salvar o orçamento padrão")
      return data
    },
    onSuccess: () => invalidar(qc),
  })
}

/** Edita o limite e/ou a supressão **do mês** (linha materializada), não o padrão do
 *  orçamento. `suprimido` remove/restaura a categoria só deste mês, sem tocar no padrão. */
export function useAtualizarLimiteMensal() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (args: {
      id: number
      limite_centavos?: number
      suprimido?: boolean
      notificar?: boolean
    }) => {
      const { id, limite_centavos, suprimido, notificar } = args
      const body: {
        limite_centavos?: number
        editado_manualmente?: boolean
        suprimido?: boolean
        notificar?: boolean
      } = {}
      if (limite_centavos !== undefined) {
        body.limite_centavos = limite_centavos
        body.editado_manualmente = true
      }
      if (suprimido !== undefined) body.suprimido = suprimido
      if (notificar !== undefined) body.notificar = notificar
      const { data, error } = await api.PATCH(
        "/api/orcamentos-mensais/{item_id}",
        {
          params: { path: { item_id: id } },
          body,
        }
      )
      if (error || !data) throw new Error("falha ao salvar o limite do mês")
      return data
    },
    onSuccess: () => invalidar(qc),
  })
}

/** Cria uma linha de orçamento **só deste mês**, a partir de um `Orcamento` já existente
 *  (padrão ou pontual) — usado por "Editar mês" ao adicionar uma categoria nova. */
export function useCriarLimiteMensal() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (
      body: OrcamentoMensalCreate
    ): Promise<OrcamentoMensal> => {
      const { data, error } = await api.POST("/api/orcamentos-mensais", {
        body,
      })
      if (error || !data) throw new Error("falha ao criar o orçamento do mês")
      return data
    },
    onSuccess: () => invalidar(qc),
  })
}

/** Aplica o orçamento padrão a um mês específico, sob pedido — a materialização automática só
 *  cobre o mês corrente (§4.6); isso é pra preencher um mês passado sem nada configurado. */
export function useMaterializarMes() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (args: {
      ano: number
      mes: number
    }): Promise<OrcamentoConsumo> => {
      const { data, error } = await api.POST("/api/orcamentos/materializar", {
        params: { query: { ano: args.ano, mes: args.mes } },
      })
      if (error || !data)
        throw new Error("falha ao aplicar o orçamento padrão a este mês")
      return data
    },
    onSuccess: () => invalidar(qc),
  })
}

export function useRemoverOrcamento() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: number) => {
      const { error } = await api.DELETE("/api/orcamentos/{orcamento_id}", {
        params: { path: { orcamento_id: id } },
      })
      if (error) throw new Error("falha ao remover o orçamento")
    },
    onSuccess: () => invalidar(qc),
  })
}
