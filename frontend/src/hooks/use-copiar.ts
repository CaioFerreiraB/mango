import { useState } from "react"
import { toast } from "sonner"

/** Copia para a área de transferência e sinaliza "copiado" por um instante. */
export function useCopiar() {
  const [copiado, setCopiado] = useState(false)
  return {
    copiado,
    copiar: (texto: string) => {
      // `clipboard` só existe em contexto seguro (HTTPS/localhost); pode também ser negado.
      if (!navigator.clipboard) {
        toast.error("Não foi possível copiar neste navegador.")
        return
      }
      navigator.clipboard.writeText(texto).then(
        () => {
          setCopiado(true)
          setTimeout(() => setCopiado(false), 1500)
        },
        () => toast.error("Não foi possível copiar.")
      )
    },
  }
}
