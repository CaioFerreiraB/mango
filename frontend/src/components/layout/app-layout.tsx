import { useEffect } from "react"
import { Outlet } from "react-router"

import { ChatPanel } from "@/components/chat/chat-panel"
import { ChatProvider } from "@/components/chat/chat-provider"
import { AppHeader } from "@/components/layout/app-header"
import { AppSidebar } from "@/components/layout/app-sidebar"
import { BottomNav } from "@/components/layout/bottom-nav"
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar"
import { aplicarAccent } from "@/lib/accent"
import { useMe } from "@/lib/api/auth"

/** App shell: sidebar + header fixos, conteúdo da rota no `Outlet`, assistente à direita. */
export function AppLayout() {
  const me = useMe()
  // Sincroniza o accent do servidor (corrige cache local em outro dispositivo/usuário).
  useEffect(() => {
    if (me.data) aplicarAccent(me.data.accent)
  }, [me.data])
  return (
    <ChatProvider>
      <SidebarProvider>
        <AppSidebar />
        {/* min-w-0: sem ele o item flex não encolhe abaixo do conteúdo (gráficos têm largura em px)
            e, ao abrir o chat, a página vaza para a direita e empurra o painel para fora da tela. */}
        <SidebarInset className="min-w-0">
          <AppHeader />
          {/* pb no mobile: a barra de atalhos flutua (`fixed`, 0.75rem acima da borda) e cobriria o fim do conteúdo. */}
          <main className="flex-1 p-4 pb-[calc(var(--bottom-nav-h)+env(safe-area-inset-bottom)+1.75rem)] md:p-6 md:pb-6">
            {/* @container: as telas medem o espaço DISPONÍVEL (janela − sidebar − chat) com @xl/@5xl…,
                em vez de breakpoints da janela, que erram com o chat aberto. */}
            <div className="@container mx-auto w-full max-w-[100rem]">
              <Outlet />
            </div>
          </main>
          <BottomNav />
        </SidebarInset>
        {/* Irmão do inset (não um 2º `Sidebar`, que dividiria o `open` com o menu da esquerda). */}
        <ChatPanel />
      </SidebarProvider>
    </ChatProvider>
  )
}
