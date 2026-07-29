import { cn } from "@/lib/utils"

/**
 * Barra de progresso (0–100). Acessível (role="progressbar" + aria-value*). `indicatorClassName`
 * colore o preenchimento — usado para os limiares de alerta de orçamento (§4.6).
 */
export function Progress({
  value,
  className,
  indicatorClassName,
}: {
  value: number
  className?: string
  indicatorClassName?: string
}) {
  const pct = Math.min(Math.max(value, 0), 100)
  return (
    <div
      role="progressbar"
      aria-valuenow={Math.round(pct)}
      aria-valuemin={0}
      aria-valuemax={100}
      className={cn("h-2 w-full overflow-hidden rounded-full bg-primary/10", className)}
    >
      <div
        className={cn("h-full rounded-full bg-primary transition-all", indicatorClassName)}
        style={{ width: `${pct}%` }}
      />
    </div>
  )
}
