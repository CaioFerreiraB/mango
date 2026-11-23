import { ArrowDownRight, ArrowUpRight } from "lucide-react"

import { Valor } from "@/components/common/valor"
import { AreaTendencia, type CampoSerie } from "@/components/dashboard/graficos"
import { Card, CardContent } from "@/components/ui/card"
import { useIsMobile } from "@/hooks/use-mobile"
import type { SerieBucket } from "@/lib/api/dashboard"
import { cn } from "@/lib/utils"

/**
 * Variação vs. mesmo período do mês anterior. Pílula **neutra** (identidade sóbria): a direção é
 * dada pela seta e pelo sinal, nunca só por cor (a11y, DESIGN.md). `delta` já vem como fração.
 */
function Delta({ delta }: { delta: number }) {
  const sobe = delta > 0
  const Icone = sobe ? ArrowUpRight : ArrowDownRight
  return (
    <span
      className="inline-flex shrink-0 items-center gap-0.5 rounded-full border px-2 py-0.5 text-xs font-medium text-muted-foreground tabular-nums"
      title="Comparado ao mesmo período do mês anterior"
    >
      {delta === 0 ? (
        "0%"
      ) : (
        <>
          <Icone className="size-3" aria-hidden />
          {`${sobe ? "+" : "−"}${Math.abs(delta * 100).toFixed(0)}%`}
        </>
      )}
    </span>
  )
}

/**
 * Card de KPI do painel: rótulo, valor grande (mês até hoje) com a variação ao lado, e uma
 * mini-área da tendência dos últimos 6 meses do mesmo dado. O saldo usa o mesmo card sem `delta`
 * nem `serie` (saldo vivo, sem base de comparação nem histórico mensal).
 */
export function KpiCard({
  label,
  centavos,
  sinal = false,
  delta,
  serie,
  campo,
}: {
  label: string
  centavos: number
  sinal?: boolean
  delta?: number | null
  serie?: SerieBucket[]
  campo?: CampoSerie
}) {
  // Mobile: card compacto, dois por linha e sem a mini-área (o gráfico nem monta).
  const compacto = useIsMobile()
  const temArea =
    !compacto && serie != null && campo != null && serie.length > 0
  return (
    // Com área: `pb-0` + `overflow-hidden` fazem a área sangrar até a borda inferior arredondada.
    <Card
      className={cn(
        compacto && "gap-0 py-4",
        temArea && "overflow-hidden pb-0"
      )}
    >
      <CardContent className={cn("space-y-3", compacto && "px-4")}>
        <div className="space-y-1">
          <p
            className={cn(
              "truncate text-muted-foreground",
              compacto ? "text-xs" : "text-sm"
            )}
          >
            {label}
          </p>
          {/* Valor sempre neutro e forte (identidade da referência): o sinal +/− carrega o
              sentido, nunca a cor — `text-foreground` sobrepõe a cor por sinal do `Valor` (a11y). */}
          <div
            className={cn(
              "flex flex-wrap items-baseline gap-x-2 gap-y-1 tracking-tight",
              compacto ? "text-lg" : "text-2xl"
            )}
          >
            <Valor
              centavos={centavos}
              sinal={sinal}
              className="font-bold whitespace-nowrap text-foreground"
            />
            {delta != null ? <Delta delta={delta} /> : null}
          </div>
        </div>
        {temArea && serie && campo ? (
          <div className="-mx-6">
            <AreaTendencia buckets={serie} campo={campo} />
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}
