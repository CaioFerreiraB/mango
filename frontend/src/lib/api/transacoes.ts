import {
  useMutation,
  useQueryClient,
  useQuery,
  keepPreviousData,
} from "@tanstack/react-query"

import { assinaturasKeys } from "@/lib/api/assinaturas"
import { api } from "@/lib/api/client"
import { mensagemErro } from "@/lib/api/erros"
import type { InvestimentoTransacao } from "@/lib/api/investimentos"
import type { components } from "@/lib/api/schema"

export type Transacao = components["schemas"]["TransacaoRead"]
export type TransacaoListagem = components["schemas"]["TransacaoListagem"]
export type TransacaoUpdate = components["schemas"]["TransacaoUpdate"]

/**
 * Valor em reais para exibir: em compra internacional o `amount_centavos` é a moeda estrangeira;
 * o valor convertido que entrou na conta/fatura vem em `amount_in_account_currency_centavos`
 * (nulo → transação doméstica, cai no `amount_centavos`).
 */
export const valorEfetivoCentavos = (t: Transacao): number =>
  t.amount_in_account_currency_centavos ?? t.amount_centavos

/** Texto do banco: o normalizado do Pluggy e, se o conector não mandar, o cru do extrato. */
export const descricaoBanco = (t: Transacao): string | null =>
  t.description ?? t.description_raw ?? null

/** Texto principal da transação: a descrição escrita pelo usuário, senão a que veio do banco. */
export const descricaoExibida = (t: Transacao): string | null =>
  t.descricao_usuario ?? descricaoBanco(t)

/** Linha secundária: com descrição própria, a do banco vira o subtítulo; senão, o estabelecimento. */
export const subtituloTransacao = (t: Transacao): string | null =>
  (t.descricao_usuario
    ? (descricaoBanco(t) ?? t.merchant_nome)
    : t.merchant_nome) ?? null

export type TransacaoFiltro = {
  inicio?: string
  fim?: string
  conta_id?: number
  categoria_id?: string
  fatura_id?: number
  tipo?: "DEBIT" | "CREDIT"
  /** Filtro cru da coluna. Para "está na fila de revisão?" use `pendente_revisao` (§4.3). */
  revisada?: boolean
  /** Não revisada E a partir da data de corte do usuário (`perfil.revisao_desde`). */
  pendente_revisao?: boolean
  eh_transferencia?: boolean
  /** Esconde o pagamento de fatura de cartão (categoria efetiva 05100000, §4.4). */
  ocultar_pagamento_fatura?: boolean
  /** Esconde lançamentos com data depois de hoje — parcelas futuras, sobretudo (§4.2). */
  ocultar_futuras?: boolean
  assinatura_id?: number
  tem_assinatura?: boolean
  busca?: string
  order?: "date" | "amount_centavos"
  descendente?: boolean
  limit?: number
  offset?: number
}

export function useTransacoes(filtro: TransacaoFiltro = {}) {
  return useQuery({
    queryKey: ["transacoes", filtro],
    placeholderData: keepPreviousData, // paginação sem "piscar" a tabela
    queryFn: async (): Promise<TransacaoListagem> => {
      const { data, error } = await api.GET("/api/transacoes", {
        params: { query: filtro },
      })
      if (error || !data) throw new Error("falha ao carregar transações")
      return data
    },
  })
}

/** Proventos de investimento candidatos a serem esta transação (mesmo valor, data ±5 dias, §4.9). */
export function useProventosSugeridos(
  transacaoId: number | null,
  enabled = true
) {
  return useQuery({
    queryKey: ["transacoes", transacaoId, "proventos-sugeridos"],
    enabled: transacaoId != null && enabled,
    queryFn: async (): Promise<InvestimentoTransacao[]> => {
      const { data, error } = await api.GET(
        "/api/transacoes/{transacao_id}/proventos-sugeridos",
        { params: { path: { transacao_id: transacaoId! } } }
      )
      if (error || !data) throw new Error("falha ao buscar proventos sugeridos")
      return data
    },
  })
}

/** Update estreito (§4.5): flags + override de categoria. Revalida a lista e o dashboard. */
export function useAtualizarTransacao() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (args: {
      id: number
      patch: TransacaoUpdate
    }): Promise<Transacao> => {
      const { data, error } = await api.PATCH(
        "/api/transacoes/{transacao_id}",
        {
          params: { path: { transacao_id: args.id } },
          body: args.patch,
        }
      )
      if (error || !data)
        throw new Error(mensagemErro(error, "falha ao salvar a transação"))
      return data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["transacoes"] })
      qc.invalidateQueries({ queryKey: ["dashboard"] })
      // Trocar categoria muda o consumo do orçamento e as séries do dashboard — sem invalidar
      // aqui, a Visão Geral seguia mostrando o número antigo até a próxima navegação.
      qc.invalidateQueries({ queryKey: ["dashboard-series"] })
      qc.invalidateQueries({ queryKey: ["orcamentos"] })
    },
  })
}

/** Marca transações como "não é assinatura" (§4.7): suprime detecção e sugestões. Batch de PATCH
 *  tolerante a falha parcial (`allSettled`); revalida transações e a busca de candidatas. */
export function useMarcarNaoAssinatura() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (ids: number[]) => {
      const res = await Promise.allSettled(
        ids.map((id) =>
          api.PATCH("/api/transacoes/{transacao_id}", {
            params: { path: { transacao_id: id } },
            body: { nao_e_assinatura: true },
          })
        )
      )
      const marcadas = res.filter(
        (r) => r.status === "fulfilled" && !r.value.error
      ).length
      return { marcadas, falhas: ids.length - marcadas }
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["transacoes"] })
      qc.invalidateQueries({ queryKey: assinaturasKeys.candidatos })
    },
  })
}
