import { useSyncExternalStore } from "react"

const MQ = "(prefers-reduced-motion: reduce)"
const assinar = (avisar: () => void) => {
  const mq = window.matchMedia?.(MQ)
  mq?.addEventListener("change", avisar)
  return () => mq?.removeEventListener("change", avisar)
}
const ler = () => !!window.matchMedia?.(MQ).matches

/** `prefers-reduced-motion: reduce`, observado ao vivo (mudar a preferência reage na hora). */
export const useMovimentoReduzido = () => useSyncExternalStore(assinar, ler)
