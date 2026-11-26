import {
  MessageSquareTextIcon,
  PanelRightCloseIcon,
  PanelRightOpenIcon,
} from "lucide-react"
import { useEffect, useRef, useState, useSyncExternalStore } from "react"
import { useLocation, useNavigate } from "react-router"

import { AcoesPainel, ChatView } from "@/components/chat/chat-view"
import { useChat } from "@/components/chat/use-chat"
import { BOTAO_TOPO_MOBILE } from "@/components/layout/topo"
import { Button } from "@/components/ui/button"
import { useMe } from "@/lib/api/auth"
import { cn } from "@/lib/utils"

const ID_BOTAO = "chat-toggle"
// Painel (encaixado ou gaveta) só a partir de lg: abaixo disso (celular e tablet, ex.: iPad mini
// 768px) a gaveta cobriria quase toda a página — o assistente abre como página própria (`/chat`).
const PAINEL_MQ = "(min-width: 1024px)"
const desktop = () => window.matchMedia(PAINEL_MQ).matches
const assinarMq = (avisar: () => void) => {
  const mq = window.matchMedia(PAINEL_MQ)
  mq.addEventListener("change", avisar)
  return () => mq.removeEventListener("change", avisar)
}
const usePainelCabe = () => useSyncExternalStore(assinarMq, desktop)

/**
 * Botão da topbar (canto superior direito). ≥ lg: alterna o painel (gaveta até xl, encaixado depois).
 * < lg (celular/tablet): abre `/chat` como página — rota própria, então o voltar do sistema fecha.
 */
export function ChatToggle() {
  const me = useMe()
  const painelCabe = usePainelCabe()
  const { painelAberto, setPainelAberto } = useChat()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  if (me.data?.tipo !== "completo" || pathname === "/chat") return null
  const expandido = painelCabe && painelAberto
  return (
    <Button
      id={ID_BOTAO}
      variant="ghost"
      size="icon-sm"
      className={BOTAO_TOPO_MOBILE}
      aria-label={expandido ? "Fechar assistente" : "Abrir assistente"}
      aria-expanded={expandido}
      title="Assistente"
      onClick={() =>
        desktop() ? setPainelAberto(!painelAberto) : navigate("/chat")
      }
    >
      <MessageSquareTextIcon className="lg:hidden" />
      {expandido ? (
        <PanelRightCloseIcon className="hidden lg:block" />
      ) : (
        <PanelRightOpenIcon className="hidden lg:block" />
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
  const aberto = painelAberto && pathname !== "/chat"
  // Monta o chat só na 1ª abertura e o mantém depois (fechar não perde a conversa nem a animação).
  const [montado, setMontado] = useState(aberto)
  if (aberto && !montado) setMontado(true)
  // Ao ABRIR (não no 1º render, que pode vir aberto do estado salvo), o foco vai para o campo do
  // assistente: entre lg e xl a gaveta cobre o botão que a abriu e o foco ficaria escondido.
  // Sem prender o foco — a gaveta não é modal.
  const painel = useRef<HTMLElement>(null)
  const abertoAntes = useRef(aberto)
  useEffect(() => {
    if (aberto && !abertoAntes.current) {
      const id = requestAnimationFrame(() =>
        painel.current?.querySelector<HTMLElement>("textarea")?.focus()
      )
      abertoAntes.current = aberto
      return () => cancelAnimationFrame(id)
    }
    abertoAntes.current = aberto
  }, [aberto])
  if (me.data?.tipo !== "completo") return null
  const fechar = () => {
    setPainelAberto(false)
    document.getElementById(ID_BOTAO)?.focus()
  }
  return (
    // Abre/fecha animando a largura, como a sidebar (200ms linear); o conteúdo fica ancorado à
    // direita com largura fixa, então desliza para dentro em vez de se espremer. Fechado = inert.
    <aside
      ref={painel}
      aria-label="Assistente"
      aria-hidden={!aberto}
      inert={!aberto}
      className={cn(
        // < xl não há espaço para encaixar (sidebar + painel deixariam ~150px de página): abre por
        // cima, como gaveta. ≥ xl encaixa ao lado e a página encolhe.
        "fixed inset-y-0 right-0 z-40 hidden h-svh shrink-0 overflow-hidden transition-[width] duration-200 ease-linear motion-reduce:transition-none lg:block xl:sticky xl:top-0 xl:z-auto",
        aberto ? "w-[360px] lg:w-[420px]" : "w-0"
      )}
      onKeyDown={(e) => {
        // Esc vindo de popover/diálogo (portais) não é DOM do painel: não fecha o painel junto.
        if (e.key === "Escape" && e.currentTarget.contains(e.target as Node))
          fechar()
      }}
    >
      <div className="absolute inset-y-0 right-0 flex w-[360px] py-2 pr-2 lg:w-[420px]">
        <div className="flex min-h-0 w-full flex-col overflow-hidden rounded-xl bg-background shadow-2xl ring-1 ring-border xl:shadow-sm xl:ring-0">
          {montado ? (
            <ChatView
              variante="painel"
              acoes={
                <AcoesPainel
                  onExpandir={() => navigate("/chat")}
                  onFechar={fechar}
                />
              }
            />
          ) : null}
        </div>
      </div>
    </aside>
  )
}
