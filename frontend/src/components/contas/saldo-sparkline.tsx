import { useId } from "react"
import { Area, AreaChart, XAxis } from "recharts"

import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart"
import type { SaldoDiarioPonto } from "@/lib/api/contas"
import { formatBRL, formatDate } from "@/lib/format"

const config: ChartConfig = { saldo: { label: "Saldo", color: "var(--primary)" } }

/**
 * Saldo em conta dos últimos dias como área compacta (sparkline). Mesma receita da `AreaTendencia`
 * do painel: linha na cor primária + degradê que some, sem eixos (DESIGN.md "Restrained"). Vazio ou
 * série chapada → `null` (o card fica só com a identidade). */
export function SaldoSparkline({ pontos }: { pontos: SaldoDiarioPonto[] }) {
  const grad = useId()
  if (pontos.length < 2) return null
  const semMovimento =
    typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-reduced-motion: reduce)").matches

  return (
    <ChartContainer config={config} className="aspect-auto h-16 w-full">
      <AreaChart data={pontos} margin={{ top: 4, right: 0, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id={grad} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--color-saldo)" stopOpacity={0.3} />
            <stop offset="100%" stopColor="var(--color-saldo)" stopOpacity={0} />
          </linearGradient>
        </defs>
        <XAxis dataKey="data" hide />
        <ChartTooltip
          content={
            <ChartTooltipContent
              labelFormatter={(_, [item]) => formatDate(String(item?.payload?.data))}
              formatter={(value) => (
                <span className="font-medium tabular-nums">{formatBRL(Number(value))}</span>
              )}
            />
          }
        />
        <Area
          dataKey="saldo_centavos"
          type="monotone"
          stroke="var(--color-saldo)"
          strokeWidth={2}
          fill={`url(#${grad})`}
          dot={false}
          isAnimationActive={!semMovimento}
        />
      </AreaChart>
    </ChartContainer>
  )
}
