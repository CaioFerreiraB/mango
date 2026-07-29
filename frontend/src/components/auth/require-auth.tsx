import { Loader2 } from "lucide-react"
import { Navigate, Outlet } from "react-router"

import { useMe, useSetupStatus } from "@/lib/api/auth"

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
 * Portão do app (§4.1, §5.2): sem instância configurada → `/setup`; configurada e sem sessão
 * (self-hosted) → `/login`. No modo local o usuário é implícito e o portão sempre libera.
 */
export function RequireAuth() {
  const status = useSetupStatus()
  const me = useMe()

  if (status.isPending) return <Carregando />
  if (status.data && !status.data.configured)
    return <Navigate to="/setup" replace />

  const precisaLogin = status.data?.app_mode === "self_hosted"
  if (precisaLogin) {
    if (me.isPending) return <Carregando />
    if (!me.data) return <Navigate to="/login" replace />
  }

  return <Outlet />
}
