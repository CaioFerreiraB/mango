import { formatBRL } from "@/lib/format"
import { cn } from "@/lib/utils"

/**
 * Valor monetário (centavos → BRL). Cor por sinal, **sempre** com o sinal visível — cor nunca é o
 * único portador de sentido (acessibilidade, DESIGN.md). `sinal` prefixa `+` em créditos.
 */
export function Valor({
  centavos,
  sinal = false,
  neutro = false,
  oculto = false,
  className,
}: {
  centavos: number
  sinal?: boolean
  /** Sem cor por sinal — usa a cor de texto padrão (o `sinal` já carrega o sentido). */
  neutro?: boolean
  /** Modo privacidade: mascara o número (mantém o layout), sem cor por sinal. */
  oculto?: boolean
  className?: string
}) {
  const cor =
    oculto || neutro
      ? undefined
      : centavos < 0
        ? "text-negative"
        : centavos > 0
          ? "text-positive"
          : "text-muted-foreground"
  const texto = oculto
    ? "R$ ••••"
    : sinal && centavos > 0
      ? `+${formatBRL(centavos)}`
      : formatBRL(centavos)
  return (
    <span className={cn("font-medium tabular-nums", cor, className)}>
      {texto}
    </span>
  )
}
