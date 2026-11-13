import { useState } from "react"

/** Copia para a área de transferência e sinaliza "copiado" por um instante. */
export function useCopiar() {
  const [copiado, setCopiado] = useState(false)
  return {
    copiado,
    copiar: (texto: string) => {
      void navigator.clipboard?.writeText(texto).then(() => {
        setCopiado(true)
        setTimeout(() => setCopiado(false), 1500)
      })
    },
  }
}
