import * as React from "react"

import { Input } from "@/components/ui/input"
import { formatBRL } from "@/lib/format"

/**
 * Input de valor monetário (centavos ↔ "R$ 0,00"). Digita-se só dígitos: cada tecla nova empurra os
 * centavos pra esquerda (ex.: "1" → R$ 0,01, "12345" → R$ 123,45), como em apps bancários. Backspace
 * remove um dígito por vez naturalmente, já que o valor exibido é sempre recomputado a partir do que
 * sobrou. Irmão do `Valor` (exibição, `@/components/common/valor`) — aqui é a versão editável.
 */
export function CurrencyInput({
  value,
  onChange,
  ...props
}: {
  /** Valor em centavos. */
  value: number
  /** Chamado com o novo valor em centavos a cada tecla. */
  onChange: (centavos: number) => void
} & Omit<React.ComponentProps<"input">, "value" | "onChange" | "type">) {
  const ref = React.useRef<HTMLInputElement>(null)
  const texto = formatBRL(value)

  // O texto inteiro é reformatado a cada tecla — o cursor sempre volta pro fim, senão o usuário
  // acabaria editando "no meio" de um valor que muda de posição a cada dígito.
  React.useEffect(() => {
    const el = ref.current
    if (el && document.activeElement === el) {
      el.setSelectionRange(texto.length, texto.length)
    }
  }, [texto])

  return (
    <Input
      {...props}
      ref={ref}
      type="text"
      inputMode="numeric"
      value={texto}
      onChange={(e) => {
        const digitos = e.target.value.replace(/\D/g, "")
        const centavos =
          digitos === ""
            ? 0
            : Math.min(Number(digitos), Number.MAX_SAFE_INTEGER)
        onChange(centavos)
      }}
    />
  )
}
