import {
  MessageSquareTextIcon,
  PanelRightCloseIcon,
  PanelRightOpenIcon,
} from "lucide-react"
import { useLocation, useNavigate } from "react-router"

import { AcoesPainel, ChatView } from "@/components/chat/chat-view"
import { useChat } from "@/components/chat/use-chat"
import { Button } from "@/components/ui/button"
import { useIsMobile } from "@/hooks/use-mobile"
import { useMe } from "@/lib/api/auth"

const ID_BOTAO = "chat-toggle"
const desktop = () => window.matchMedia("(min-width: 768px)").matches

/**
 * Botão da topbar (canto superior direito). Desktop: alterna o painel encaixado. Mobile: abre
 * `/chat` em tela cheia — rota própria, então o voltar do sistema fecha.
 */
export function ChatToggle() {
  const me = useMe()
  const mobile = useIsMobile()
  const { painelAberto, setPainelAberto } = useChat()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  if (me.data?.tipo !== "completo" || pathname === "/chat") return null
  const expandido = !mobile && painelAberto
  return (
    <Button
      id={ID_BOTAO}
      variant="ghost"
      size="icon-sm"
      aria-label={expandido ? "Fechar assistente" : "Abrir assistente"}
      aria-expanded={expandido}
      title="Assistente"
      onClick={() =>
        desktop() ? setPainelAberto(!painelAberto) : navigate("/chat")
      }
    >
      <MessageSquareTextIcon className="md:hidden" />
      {expandido ? (
        <PanelRightCloseIcon className="hidden md:block" />
      ) : (
        <PanelRightOpenIcon className="hidden md:block" />
      )}
    </Button>
  )
}

/** Painel encaixado à direita (só ≥ md; visibilidade por CSS, como a bottom nav). */
export function ChatPanel() {
  const { painelAberto, setPainelAberto } = useChat()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const me = useMe()
  if (!painelAberto || pathname === "/chat" || me.data?.tipo !== "completo")
    return null
  const fechar = () => {
    setPainelAberto(false)
    document.getElementById(ID_BOTAO)?.focus()
  }
  return (
    <aside
      aria-label="Assistente"
      className="sticky top-0 hidden h-svh w-[360px] shrink-0 py-2 pr-2 md:flex lg:w-[420px]"
      onKeyDown={(e) => {
        // Esc vindo de popover/diálogo (portais) não é DOM do painel: não fecha o painel junto.
        if (e.key === "Escape" && e.currentTarget.contains(e.target as Node))
          fechar()
      }}
    >
      <div className="flex min-h-0 w-full flex-col overflow-hidden rounded-xl bg-background shadow-sm">
        <ChatView
          variante="painel"
          acoes={
            <AcoesPainel
              onExpandir={() => navigate("/chat")}
              onFechar={fechar}
            />
          }
        />
      </div>
    </aside>
  )
}
