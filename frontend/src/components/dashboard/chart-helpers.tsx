import type { ChartConfig } from "@/components/ui/chart"
import { formatBRL } from "@/lib/format"

const compacto = new Intl.NumberFormat("pt-BR", {
  notation: "compact",
  maximumFractionDigits: 1,
})

/** Formata o tick do eixo Y (centavos → reais compacto). Ex.: 123456 → `1,2 mil`. */
export const eixoBRL = (centavos: number) => compacto.format(centavos / 100)

/** Uma linha do tooltip: swatch + rótulo + valor em BRL (valores trafegam em centavos). */
export function linhaTooltip(
  valor: unknown,
  nome: string,
  cor: string | undefined,
  config: ChartConfig
) {
  return (
    <>
      <span
        className="mt-0.5 size-2.5 shrink-0 rounded-[2px]"
        style={{ background: cor }}
        aria-hidden
      />
      <div className="flex flex-1 items-center justify-between gap-2 leading-none">
        <span className="text-muted-foreground">
          {config[nome]?.label ?? nome}
        </span>
        <span className="font-mono font-medium text-foreground tabular-nums">
          {formatBRL(Number(valor))}
        </span>
      </div>
    </>
  )
}
