import { Loader2 } from "lucide-react"
import { Navigate, Outlet, useLocation } from "react-router"

import { useMe, useSetupStatus } from "@/lib/api/auth"

/** Rotas que uma conta `tipo="divisao"` (§4.11) pode abrir — o resto redireciona pra `/divisoes`,
 * que também é a página inicial dessa conta (`/` não está na lista). */
const ROTAS_PERMITIDAS_DIVISAO = ["/divisoes", "/configuracoes"]

function permitidoParaDivisao(pathname: string): boolean {
  return ROTAS_PERMITIDAS_DIVISAO.some(
    (rota) => pathname === rota || pathname.startsWith(`${rota}/`)
  )
}

function Carregando() {
  return (
    <div
      className="flex min-h-svh items-center justify-center"
      role="status"
      aria-live="polite"
    >
      <Loader2
        className="size-6 animate-spin text-muted-foreground"
        aria-hidden
      />
      <span className="sr-only">Carregando…</span>
    </div>
  )
}

/**
 * Portão das rotas públicas de autenticação (`/login`, `/recuperar-senha`, `/convite/:token`):
 * sem instância configurada não há o que autenticar → `/setup`. O `/setup` faz o caminho inverso
 * (já configurado → `/`), então nenhuma URL digitada à mão escapa do first-run.
 */
export function RequireSetup() {
  const status = useSetupStatus()

  if (status.isPending) return <Carregando />
  if (status.data && !status.data.configured)
    return <Navigate to="/setup" replace />

  return <Outlet />
}

/**
 * Portão do app (§4.1, §5.2): sem instância configurada → `/setup`; configurada e sem sessão
 * (self-hosted) → `/login`. No modo local o usuário é implícito e o portão sempre libera.
 */
export function RequireAuth() {
  const status = useSetupStatus()
  const me = useMe()
  const { pathname } = useLocation()

  if (status.isPending) return <Carregando />
  if (status.data && !status.data.configured)
    return <Navigate to="/setup" replace />

  const precisaLogin = status.data?.app_mode === "self_hosted"
  if (precisaLogin) {
    if (me.isPending) return <Carregando />
    if (!me.data) return <Navigate to="/login" replace />
  }

  // Conta "divisao" (§4.11): página inicial é Divisão de contas, não o Dashboard — e não navega
  // pro resto do app mesmo digitando a URL direto (defesa em profundidade; o backend já barra
  // com 403 em `exigir_usuario_completo`).
  if (me.data?.tipo === "divisao" && !permitidoParaDivisao(pathname)) {
    return <Navigate to="/divisoes" replace />
  }

  return <Outlet />
}
