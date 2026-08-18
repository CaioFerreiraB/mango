import { useMutation, useQuery } from "@tanstack/react-query"

import { api } from "@/lib/api/client"
import { mensagemErro } from "@/lib/api/erros"
import type { components } from "@/lib/api/schema"

export type Me = components["schemas"]["MeRead"]
export type SetupStatus = components["schemas"]["SetupStatus"]
export type LoginResponse = components["schemas"]["LoginResponse"]

export const authKeys = {
  setupStatus: ["setup-status"] as const,
  me: ["me"] as const,
}

/** Estado do first-run: se a instância já foi configurada e em que modo roda. */
export function useSetupStatus() {
  return useQuery({
    queryKey: authKeys.setupStatus,
    queryFn: async (): Promise<SetupStatus> => {
      const { data, error } = await api.GET("/api/setup/status")
      if (error || !data) throw new Error("falha ao consultar status do setup")
      return data
    },
  })
}

/** Usuário logado, ou `null` quando não autenticado (401). */
export function useMe() {
  return useQuery({
    queryKey: authKeys.me,
    queryFn: async (): Promise<Me | null> => {
      const { data, error } = await api.GET("/api/auth/me")
      return error ? null : (data ?? null)
    },
  })
}

/** Login em 2 fases (§5.2, #15): sem `codigo_totp`, a resposta pode vir com
 *  `totp_necessario: true` (senha ok, falta o código — sem sessão criada) em vez de logar. */
export function useLogin() {
  return useMutation({
    mutationFn: async (body: {
      email: string
      senha: string
      codigo_totp?: string
    }): Promise<LoginResponse> => {
      const { data, error } = await api.POST("/api/auth/login", { body })
      if (error || !data) throw new Error(mensagemErro(error, "credenciais inválidas"))
      return data
    },
  })
}

/** Recuperação de senha — só funciona para quem tem 2FA configurado (o código é a prova de
 *  posse; sem e-mail, decisão #15). */
export function useRecuperarSenha() {
  return useMutation({
    mutationFn: async (body: {
      email: string
      codigo_totp: string
      nova_senha: string
    }): Promise<void> => {
      const { error } = await api.POST("/api/auth/recuperar-senha", { body })
      if (error) throw new Error(mensagemErro(error, "não foi possível recuperar a senha"))
    },
  })
}
