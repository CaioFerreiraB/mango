import { cn } from "@/lib/utils"
import type { DespesaFixaResumo } from "@/lib/api/despesas-fixas"

/** Barra empilhada pagas | em aberto | atrasadas (por quantidade). O texto ao lado repete os
 *  números — a cor não é o único sinal. */
export function BarraMes({
  resumo,
  sobreEscuro = false,
}: {
  resumo: DespesaFixaResumo
  /** Dentro do herói escuro: trilha e "em aberto" em branco translúcido. */
  sobreEscuro?: boolean
}) {
  const { pagas, abertas, atrasadas } = resumo
  const total = pagas.qtd + abertas.qtd + atrasadas.qtd
  if (!total) return null
  const pct = (n: number) => `${(n / total) * 100}%`
  return (
    <div
      role="img"
      aria-label={`${pagas.qtd} pagas, ${abertas.qtd} em aberto, ${atrasadas.qtd} atrasadas`}
      className={cn(
        "flex h-2.5 w-full overflow-hidden rounded-full",
        sobreEscuro ? "bg-white/15" : "bg-muted"
      )}
    >
      <span className="bg-success" style={{ width: pct(pagas.qtd) }} />
      <span
        className={sobreEscuro ? "bg-white/45" : "bg-muted-foreground"}
        style={{ width: pct(abertas.qtd) }}
      />
      <span className="bg-negative" style={{ width: pct(atrasadas.qtd) }} />
    </div>
  )
}
