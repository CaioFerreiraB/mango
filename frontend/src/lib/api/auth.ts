import { useQuery } from "@tanstack/react-query"

import { api } from "@/lib/api/client"
import type { components } from "@/lib/api/schema"

export type Me = components["schemas"]["MeRead"]
export type SetupStatus = components["schemas"]["SetupStatus"]

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
