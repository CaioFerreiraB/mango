import type { DespesaFixaResumo } from "@/lib/api/despesas-fixas"

/** Barra empilhada pagas | em aberto | atrasadas (por quantidade). O texto ao lado repete os
 *  números — a cor não é o único sinal. */
export function BarraMes({ resumo }: { resumo: DespesaFixaResumo }) {
  const { pagas, abertas, atrasadas } = resumo
  const total = pagas.qtd + abertas.qtd + atrasadas.qtd
  if (!total) return null
  const pct = (n: number) => `${(n / total) * 100}%`
  return (
    <div
      role="img"
      aria-label={`${pagas.qtd} pagas, ${abertas.qtd} em aberto, ${atrasadas.qtd} atrasadas`}
      className="flex h-2.5 w-full overflow-hidden rounded-full bg-muted"
    >
      <span className="bg-[#0ca678]" style={{ width: pct(pagas.qtd) }} />
      <span
        className="bg-muted-foreground"
        style={{ width: pct(abertas.qtd) }}
      />
      <span className="bg-negative" style={{ width: pct(atrasadas.qtd) }} />
    </div>
  )
}
