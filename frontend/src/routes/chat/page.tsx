import {
  useEffect,
  useState,
  useSyncExternalStore,
  type CSSProperties,
} from "react"
import { createPortal } from "react-dom"
import { useLocation, useNavigate } from "react-router"

import { useChat } from "@/components/chat/use-chat"
import { AcaoRecolher, ChatView } from "@/components/chat/chat-view"

/**
 * Área de fato visível da janela (`visualViewport`). Com o teclado aberto ela encolhe — no iOS e
 * no Chrome Android atual o teclado não redimensiona a página, só a área visível — e pode deslocar
 * (`offsetTop`). Seguir essa área mantém o campo de texto logo acima do teclado.
 */
function useAreaVisivel(ativo: boolean): CSSProperties | undefined {
  const [area, setArea] = useState<{ altura: number; topo: number } | null>(
    null
  )
  useEffect(() => {
    const vv = window.visualViewport
    if (!ativo || !vv) return
    const medir = () => setArea({ altura: vv.height, topo: vv.offsetTop })
    medir()
    vv.addEventListener("resize", medir)
    vv.addEventListener("scroll", medir)
    return () => {
      vv.removeEventListener("resize", medir)
      vv.removeEventListener("scroll", medir)
    }
  }, [ativo])
  if (!ativo || !area) return undefined
  // Teclado aberto: o fundo da área visível é o teclado, não a borda arredondada do aparelho —
  // o campo não precisa da folga do safe-area.
  const teclado = area.altura < window.innerHeight - 80
  return {
    height: area.altura,
    top: area.topo,
    ...(teclado && { "--fundo-seguro": "0px" }),
  } as CSSProperties
}

// Mesmo corte do `md:` (e do `useIsMobile`), mas lido já no 1º render: decidir o portal depois
// remontaria a conversa (e o foco do campo) logo após abrir.
const MOBILE = "(max-width: 767px)"
const assinarMobile = (aviso: () => void) => {
  const mql = window.matchMedia(MOBILE)
  mql.addEventListener("change", aviso)
  return () => mql.removeEventListener("change", aviso)
}
const ehMobile = () => window.matchMedia(MOBILE).matches

/**
 * `/chat`: tela cheia no mobile e conversa expandida no desktop. No mobile vai por portal para o
 * `body`: o invólucro das páginas é `@container` (contenção de layout), que prenderia o `fixed` a
 * ele em vez da tela — aí nem cobria a bottom nav nem ia até o fim da tela.
 */
export function ChatPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { setPainelAberto } = useChat()
  const mobile = useSyncExternalStore(assinarMobile, ehMobile)
  const area = useAreaVisivel(mobile)
  // Entrou direto pela URL: não há página anterior no histórico do app.
  const voltar = () =>
    location.key !== "default" ? navigate(-1) : navigate("/")
  const conteudo = (
    <div
      style={area}
      className="fixed inset-x-0 top-0 z-50 flex h-dvh flex-col bg-background pt-[env(safe-area-inset-top)] md:static md:z-auto md:h-[calc(100svh-7.5rem)] md:overflow-hidden md:rounded-xl md:border md:pt-0"
    >
      <ChatView
        variante="pagina"
        voltar={voltar}
        acoes={
          // Recolher para o painel só existe onde há painel (≥ lg, ver ChatToggle).
          <span className="hidden lg:contents">
            <AcaoRecolher
              onRecolher={() => {
                setPainelAberto(true)
                voltar()
              }}
            />
          </span>
        }
      />
    </div>
  )
  return mobile ? createPortal(conteudo, document.body) : conteudo
}
