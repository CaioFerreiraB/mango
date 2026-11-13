import { useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { useCallback, useEffect, useMemo, useRef, useState } from "react"

import {
  chaveConversas,
  pararResposta,
  transmitirMensagem,
} from "@/lib/api/chat"
import {
  type ChatContexto,
  Contexto,
  type Envio,
} from "@/components/chat/use-chat"

/**
 * Estado do chat no app shell: fica acima do painel (desktop) e da página `/chat` (mobile/expandido),
 * então a resposta em andamento sobrevive a navegar entre páginas e a alternar painel ↔ página.
 */
const CHAVE_PAINEL = "mango_chat_painel"

// `randomUUID` só existe em contexto seguro; o self-hosted pode rodar em HTTP na rede local.
function novaChave() {
  return (
    globalThis.crypto?.randomUUID?.() ??
    `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`
  )
}
const CHAVE_CONVERSA = "mango_chat_conversa"

function lerConversa() {
  try {
    const id = Number(sessionStorage.getItem(CHAVE_CONVERSA))
    return Number.isInteger(id) && id > 0 ? id : null
  } catch {
    return null
  }
}

function lerPainel() {
  try {
    return localStorage.getItem(CHAVE_PAINEL) === "1"
  } catch {
    return false
  }
}

export function ChatProvider({ children }: { children: React.ReactNode }) {
  const qc = useQueryClient()
  const [painelAberto, setPainel] = useState(lerPainel)
  // Por aba (sessionStorage): recarregar mantém a conversa aberta, como a URL de um chat.
  const [conversaId, setConversaId] = useState<number | null>(lerConversa)
  const [envio, setEnvio] = useState<Envio | null>(null)
  const abortar = useRef<AbortController | null>(null)

  const setPainelAberto = useCallback((aberto: boolean) => {
    setPainel(aberto)
    try {
      localStorage.setItem(CHAVE_PAINEL, aberto ? "1" : "0")
    } catch {
      /* armazenamento indisponível: só não lembra entre sessões */
    }
  }, [])

  const transmitir = useCallback(
    (pedido: string | null, chave: string | null) => {
      if (abortar.current) return
      const controle = new AbortController()
      abortar.current = controle
      let alvo = conversaId
      let alterou = false
      setEnvio({
        conversaId: alvo,
        pedido,
        pedidoId: null,
        chave,
        resposta: "",
        status: "Enviando…",
        erro: null,
        ativo: true,
      })
      const atualizar = (parcial: Partial<Envio>) =>
        setEnvio((e) => (e ? { ...e, ...parcial } : e))
      transmitirMensagem(
        pedido === null
          ? { conversa_id: alvo, regenerar: true }
          : { conversa_id: alvo, texto: pedido, regenerar: false, chave },
        controle.signal,
        (ev) => {
          switch (ev.tipo) {
            case "conversa":
              alvo = ev.dados.id
              setConversaId(alvo)
              atualizar({ conversaId: alvo, pedidoId: ev.dados.pedido_id })
              void qc.invalidateQueries({
                queryKey: chaveConversas,
                exact: true,
              })
              break
            case "status":
              atualizar({ status: ev.dados.texto })
              break
            case "delta":
              setEnvio((e) =>
                e
                  ? {
                      ...e,
                      status: null,
                      resposta: e.resposta + ev.dados.texto,
                    }
                  : e
              )
              break
            case "aplicada":
              alterou = true
              break
            case "erro":
              atualizar({ erro: ev.dados.mensagem, status: null })
              break
          }
        }
      )
        .then(
          () => null,
          (e: unknown) =>
            controle.signal.aborted
              ? null
              : e instanceof Error
                ? e.message
                : "Falha de conexão."
        )
        .then(async (falha) => {
          abortar.current = null
          // Escrita aplicada direto (frase exata): atualiza também as páginas de dados.
          await qc.invalidateQueries(
            alterou ? undefined : { queryKey: chaveConversas }
          )
          setEnvio((e) => {
            if (!e) return e
            const erro = falha ?? e.erro
            // Sucesso: a conversa recarregada já tem pedido e resposta. Erro: mantém para o retry.
            return erro ? { ...e, erro, ativo: false, status: null } : null
          })
        })
    },
    [conversaId, qc]
  )

  const parar = useCallback(() => {
    // O servidor salva o que já chegou; não aborta o fetch, para receber o `fim`.
    pararResposta().catch((e: Error) => toast.error(e.message))
  }, [])

  // Sair da aplicação (logout/fechar) no meio da resposta: o servidor conclui sozinho.
  useEffect(() => () => abortar.current?.abort(), [])

  useEffect(() => {
    try {
      if (conversaId === null) sessionStorage.removeItem(CHAVE_CONVERSA)
      else sessionStorage.setItem(CHAVE_CONVERSA, String(conversaId))
    } catch {
      /* sem armazenamento: só não lembra ao recarregar */
    }
  }, [conversaId])

  const valor = useMemo<ChatContexto>(
    () => ({
      painelAberto,
      setPainelAberto,
      conversaId,
      abrirConversa: (id) => {
        if (abortar.current) return
        setEnvio(null)
        setConversaId(id)
      },
      envio,
      enviar: (texto, chave) => transmitir(texto, chave ?? novaChave()),
      regenerar: () => transmitir(null, null),
      parar,
    }),
    [painelAberto, setPainelAberto, conversaId, envio, transmitir, parar]
  )
  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>
}
