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
  absoluto = false,
  quebraMoeda = false,
  className,
}: {
  centavos: number
  sinal?: boolean
  /** Sem cor por sinal — usa a cor de texto padrão (o `sinal` já carrega o sentido). */
  neutro?: boolean
  /** Modo privacidade: mascara o número (mantém o layout), sem cor por sinal. */
  oculto?: boolean
  /** Mostra `Math.abs(centavos)` (sem "-") — a cor continua vindo do sinal real, então um
   *  valor negativo ainda pode aparecer em vermelho, só sem o sinal de menos no texto. */
  absoluto?: boolean
  /** Card estreito: permite quebrar linha só entre "R$" e o número (Intl usa NBSP ali), nunca
   *  dentro do número nem depois do "-" — número partido é número ambíguo. */
  quebraMoeda?: boolean
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
  const exibido = absoluto ? Math.abs(centavos) : centavos
  const texto = oculto
    ? "R$ ••••"
    : sinal && exibido > 0
      ? `+${formatBRL(exibido)}`
      : formatBRL(exibido)
  const [moeda, numero] = texto.split("\u00a0")
  return (
    <span className={cn("font-medium tabular-nums", cor, className)}>
      {quebraMoeda && numero ? (
        <>
          <span className="whitespace-nowrap">{moeda}</span>{" "}
          <span className="whitespace-nowrap">{numero}</span>
        </>
      ) : (
        texto
      )}
    </span>
  )
}
