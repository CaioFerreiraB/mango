import { useLocation, useNavigate } from "react-router"

import { useChat } from "@/components/chat/use-chat"
import { AcaoRecolher, ChatView } from "@/components/chat/chat-view"

/**
 * `/chat`: tela cheia no mobile (cobre a bottom nav, z-50 > z-40) e conversa expandida no desktop.
 */
export function ChatPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { setPainelAberto } = useChat()
  // Entrou direto pela URL: não há página anterior no histórico do app.
  const voltar = () =>
    location.key !== "default" ? navigate(-1) : navigate("/")
  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-background pt-[env(safe-area-inset-top)] md:static md:z-auto md:h-[calc(100svh-7.5rem)] md:overflow-hidden md:rounded-xl md:border md:pt-0">
      <ChatView
        variante="pagina"
        voltar={voltar}
        acoes={
          <AcaoRecolher
            onRecolher={() => {
              setPainelAberto(true)
              voltar()
            }}
          />
        }
      />
    </div>
  )
}
