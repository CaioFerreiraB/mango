import { createContext, useContext } from "react"

export type Envio = {
  conversaId: number | null
  pedido: string | null // null = regenerar (o pedido já está na conversa)
  pedidoId: number | null // id do pedido gravado (evento `conversa`); null = não chegou ao servidor
  resposta: string
  status: string | null
  erro: string | null
  ativo: boolean
}

export type ChatContexto = {
  painelAberto: boolean
  setPainelAberto: (aberto: boolean) => void
  conversaId: number | null
  abrirConversa: (id: number | null) => void
  envio: Envio | null
  enviar: (texto: string) => void
  regenerar: () => void
  parar: () => void
}

export const Contexto = createContext<ChatContexto | null>(null)

export function useChat() {
  const ctx = useContext(Contexto)
  if (!ctx) throw new Error("useChat fora do ChatProvider")
  return ctx
}
