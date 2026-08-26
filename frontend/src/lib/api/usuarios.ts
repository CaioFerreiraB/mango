import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { api } from "@/lib/api/client"
import { mensagemErro } from "@/lib/api/erros"
import type { components } from "@/lib/api/schema"

export type UsuarioBusca = components["schemas"]["UsuarioBusca"]
export type UsuarioAdmin = components["schemas"]["UsuarioAdminRead"]
export type TipoUsuario = UsuarioAdmin["tipo"]

/** Busca usuários da instância (§4.11) — pra "com quem dividir" e a lista de pessoas. */
export function useBuscarUsuarios(q: string) {
  return useQuery({
    queryKey: ["usuarios", "buscar", q],
    queryFn: async (): Promise<UsuarioBusca[]> => {
      const { data, error } = await api.GET("/api/usuarios/buscar", {
        params: { query: { q } },
      })
      if (error || !data) throw new Error("falha ao buscar pessoas")
      return data
    },
  })
}

// --- gestão de usuários (§4.11/§5.2) — aba "Usuários" em Configurações, só o administrador ------

export const usuariosAdminKeys = {
  lista: ["usuarios", "admin"] as const,
}

function invalidarAdmin(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: usuariosAdminKeys.lista })
}

export function useUsuariosAdmin() {
  return useQuery({
    queryKey: usuariosAdminKeys.lista,
    queryFn: async (): Promise<UsuarioAdmin[]> => {
      const { data, error } = await api.GET("/api/admin/usuarios")
      if (error || !data)
        throw new Error(mensagemErro(error, "falha ao listar usuários"))
      return data
    },
  })
}

export function useCriarUsuarioAdmin() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (args: {
      nome: string
      email: string
      tipo: TipoUsuario
    }) => {
      const { data, error } = await api.POST("/api/admin/usuarios", {
        body: args,
      })
      if (error || !data)
        throw new Error(mensagemErro(error, "falha ao criar o usuário"))
      return data
    },
    onSuccess: () => invalidarAdmin(qc),
  })
}

function useMudarAtivo(path: "ativar" | "desativar") {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (usuarioId: number): Promise<UsuarioAdmin> => {
      const rota =
        path === "ativar"
          ? ("/api/admin/usuarios/{usuario_id}/ativar" as const)
          : ("/api/admin/usuarios/{usuario_id}/desativar" as const)
      const { data, error } = await api.POST(rota, {
        params: { path: { usuario_id: usuarioId } },
      })
      if (error || !data)
        throw new Error(mensagemErro(error, "falha ao atualizar o usuário"))
      return data
    },
    onSuccess: () => invalidarAdmin(qc),
  })
}

export function useAtivarUsuarioAdmin() {
  return useMudarAtivo("ativar")
}

export function useDesativarUsuarioAdmin() {
  return useMudarAtivo("desativar")
}

export function useReenviarConviteAdmin() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (usuarioId: number) => {
      const { data, error } = await api.POST(
        "/api/admin/usuarios/{usuario_id}/reenviar-convite",
        { params: { path: { usuario_id: usuarioId } } }
      )
      if (error || !data)
        throw new Error(mensagemErro(error, "falha ao gerar novo link"))
      return data
    },
    onSuccess: () => invalidarAdmin(qc),
  })
}

export function useMudarTipoUsuarioAdmin() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (args: {
      usuarioId: number
      tipo: TipoUsuario
    }): Promise<UsuarioAdmin> => {
      const { data, error } = await api.POST(
        "/api/admin/usuarios/{usuario_id}/tipo",
        {
          params: { path: { usuario_id: args.usuarioId } },
          body: { tipo: args.tipo },
        }
      )
      if (error || !data)
        throw new Error(
          mensagemErro(error, "falha ao alterar o tipo de acesso")
        )
      return data
    },
    onSuccess: () => invalidarAdmin(qc),
  })
}

export function useRemoverUsuarioAdmin() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (usuarioId: number) => {
      const { error } = await api.DELETE("/api/admin/usuarios/{usuario_id}", {
        params: { path: { usuario_id: usuarioId } },
      })
      if (error)
        throw new Error(mensagemErro(error, "falha ao excluir o usuário"))
    },
    onSuccess: () => invalidarAdmin(qc),
  })
}
