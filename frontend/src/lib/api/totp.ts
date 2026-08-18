import { useMutation, useQueryClient } from "@tanstack/react-query"

import { api } from "@/lib/api/client"
import { mensagemErro } from "@/lib/api/erros"
import type { components } from "@/lib/api/schema"

export type TotpIniciado = components["schemas"]["TotpIniciado"]

/** 2FA em Configurações (§5.2, #15): cadastrar/trocar exige reconfirmar a senha atual
 *  (step-up); habilitar a exigência no login não exige (só aumenta segurança). */

/** Passo 1 de cadastrar/trocar o 2FA — gera um novo secret e sela um ticket. */
export function useIniciarTotp() {
  return useMutation({
    mutationFn: async (senha_atual: string): Promise<TotpIniciado> => {
      const { data, error } = await api.POST("/api/perfil/totp/iniciar", {
        body: { senha_atual },
      })
      if (error || !data) throw new Error(mensagemErro(error, "senha atual incorreta"))
      return data
    },
  })
}

/** Passo 2: confirma o código do secret novo — grava (troca substitui o anterior). */
export function useConfirmarTotp() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (args: { ticket: string; codigo_totp: string }): Promise<void> => {
      const { error } = await api.POST("/api/perfil/totp/confirmar", { body: args })
      if (error) throw new Error(mensagemErro(error, "código incorreto"))
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["perfil"] })
      qc.invalidateQueries({ queryKey: ["me"] })
    },
  })
}

/** Liga a exigência de código no login — sem step-up. */
export function useHabilitarTotpLogin() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (): Promise<void> => {
      const { error } = await api.POST("/api/perfil/totp/habilitar")
      if (error) throw new Error(mensagemErro(error, "não foi possível habilitar"))
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["perfil"] })
      qc.invalidateQueries({ queryKey: ["me"] })
    },
  })
}

/** Desliga a exigência de código no login (o 2FA continua configurado p/ recuperar senha). */
export function useDesabilitarTotpLogin() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (senha_atual: string): Promise<void> => {
      const { error } = await api.POST("/api/perfil/totp/desabilitar", {
        body: { senha_atual },
      })
      if (error) throw new Error(mensagemErro(error, "senha atual incorreta"))
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["perfil"] })
      qc.invalidateQueries({ queryKey: ["me"] })
    },
  })
}
