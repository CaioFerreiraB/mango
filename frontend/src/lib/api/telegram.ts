import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { api } from "@/lib/api/client"
import { mensagemErro } from "@/lib/api/erros"
import type { components } from "@/lib/api/schema"

export type Telegram = components["schemas"]["TelegramRead"]
export type TelegramInstancia = components["schemas"]["TelegramInstanciaRead"]
export type InstanciaUpdate = components["schemas"]["TelegramInstanciaUpdate"]
export type Vinculo = components["schemas"]["VinculoRead"]

type Acao =
  | { tipo: "preferencia"; ativo: boolean }
  | { tipo: "vincular" }
  | { tipo: "confirmar"; solicitacaoId: string }
  | { tipo: "desvincular" }
  | { tipo: "testar" }
  | { tipo: "instancia"; dados: InstanciaUpdate }
  | { tipo: "remover-instancia" }
  | { tipo: "testar-instancia" }

export function useTelegram() {
  return useQuery({
    queryKey: ["telegram", "usuario"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/telegram")
      if (!data || error)
        throw new Error(mensagemErro(error, "Falha ao carregar o Telegram."))
      return data
    },
    refetchInterval: (query) =>
      query.state.data?.solicitacao_id ? 3000 : 60000,
  })
}

export function useTelegramInstancia(enabled: boolean) {
  return useQuery({
    queryKey: ["telegram", "instancia"],
    enabled,
    queryFn: async () => {
      const { data, error } = await api.GET("/api/telegram/instancia")
      if (!data || error)
        throw new Error(mensagemErro(error, "Falha ao carregar a integração."))
      return data
    },
  })
}

export function useAcaoTelegram() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (acao: Acao): Promise<Vinculo | undefined> => {
      if (acao.tipo === "vincular") {
        const { data, error, response } = await api.POST(
          "/api/telegram/vinculo"
        )
        if (!data || error)
          throw new Error(mensagemErro(error, "Falha ao criar vínculo."), {
            cause: response.status,
          })
        return data
      }
      const resultado = await (() => {
        switch (acao.tipo) {
          case "preferencia":
            return api.PATCH("/api/telegram", {
              body: { notif_nao_revisadas: acao.ativo },
            })
          case "confirmar":
            return api.POST("/api/telegram/vinculo/confirmar", {
              body: { solicitacao_id: acao.solicitacaoId },
            })
          case "desvincular":
            return api.DELETE("/api/telegram/vinculo")
          case "testar":
            return api.POST("/api/telegram/testar")
          case "instancia":
            return api.PATCH("/api/telegram/instancia", { body: acao.dados })
          case "remover-instancia":
            return api.DELETE("/api/telegram/instancia")
          case "testar-instancia":
            return api.POST("/api/telegram/instancia/testar")
        }
      })()
      if (resultado.error)
        throw new Error(
          mensagemErro(resultado.error, "Não foi possível concluir a ação."),
          { cause: resultado.response.status }
        )
      return undefined
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ["telegram"] }),
  })
}

export const errosTelegram: Record<string, string> = {
  token_invalido:
    "O token do bot não é mais válido. O administrador precisa substituí-lo.",
  destinatario_bloqueou:
    "O bot foi bloqueado no Telegram. Desbloqueie-o e ative o relatório novamente.",
  bot_em_uso:
    "O bot está sendo usado por outra aplicação ou tem um webhook ativo. Use um bot exclusivo para esta instalação.",
  webhook_ativo:
    "O bot tem um webhook ativo. Use um bot exclusivo, sem webhook.",
  sem_conexao:
    "Não foi possível conectar ao Telegram. O Mango tentará novamente.",
  limite_telegram:
    "O Telegram pediu uma pausa. A próxima tentativa respeitará esse prazo.",
  envio_incerto:
    "O Telegram não confirmou a entrega. Para evitar mensagens duplicadas, o relatório não será reenviado hoje.",
  resposta_invalida:
    "O Telegram devolveu uma resposta inesperada. Tente validar a conexão novamente.",
  requisicao_rejeitada:
    "O Telegram recusou a solicitação. Confira a configuração e teste a conexão.",
  sync_indisponivel:
    "A sincronização não terminou. O relatório aguarda uma nova tentativa.",
  erro_interno:
    "A rotina diária não terminou. Verifique as conexões e tente novamente no próximo dia.",
}
