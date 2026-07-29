import { useEffect } from "react"
import { Outlet } from "react-router"

import { AppHeader } from "@/components/layout/app-header"
import { AppSidebar } from "@/components/layout/app-sidebar"
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar"
import { aplicarAccent } from "@/lib/accent"
import { useMe } from "@/lib/api/auth"

/** App shell: sidebar + header fixos, conteúdo da rota no `Outlet`. */
export function AppLayout() {
  const me = useMe()
  // Sincroniza o accent do servidor (corrige cache local em outro dispositivo/usuário).
  useEffect(() => {
    if (me.data) aplicarAccent(me.data.accent)
  }, [me.data])
  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <AppHeader />
        <main className="flex-1 p-4 md:p-6">
          <div className="mx-auto w-full max-w-6xl">
            <Outlet />
          </div>
        </main>
      </SidebarInset>
    </SidebarProvider>
  )
}
