import { ArrowDownRight, ArrowUpRight } from "lucide-react"
import type { ReactNode } from "react"

import { CardDestaque, Kpi } from "@/components/common/kpi"
import { Valor } from "@/components/common/valor"
import { AreaTendencia, type CampoSerie } from "@/components/dashboard/graficos"
import { useIsMobile } from "@/hooks/use-mobile"
import type { SerieBucket } from "@/lib/api/dashboard"

/**
 * Variação vs. mesmo período do mês anterior. Pílula **neutra** (identidade sóbria): a direção é
 * dada pela seta e pelo sinal, nunca só por cor (a11y, DESIGN.md). `delta` já vem como fração.
 */
function Delta({ delta, titulo }: { delta: number; titulo: string }) {
  const sobe = delta > 0
  const Icone = sobe ? ArrowUpRight : ArrowDownRight
  return (
    <span
      className="inline-flex shrink-0 items-center gap-0.5 rounded-full border px-2 py-0.5 text-xs font-medium text-muted-foreground tabular-nums"
      title={titulo}
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
 * KPI de dinheiro do painel: valor (mês até hoje) com a variação ao lado e, no desktop, a
 * mini-área da tendência dos últimos 6 meses do mesmo dado. Casca = `Kpi` comum.
 */
export function KpiCard({
  label,
  centavos,
  sinal = false,
  delta,
  serie,
  campo,
  oculto = false,
  rodape,
  tituloDelta = "Comparado ao mesmo período do mês anterior",
}: {
  label: string
  centavos: number
  /** Linha de contexto sob o valor (ex.: "62% utilizado", "1–23 out"). */
  rodape?: ReactNode
  tituloDelta?: string
  /** Modo privacidade: valor mascarado (e o tooltip da mini-área também). */
  oculto?: boolean
  sinal?: boolean
  delta?: number | null
  serie?: SerieBucket[]
  campo?: CampoSerie
}) {
  // Mobile: sem a mini-área (o gráfico nem monta) — dois por linha, compactos.
  const compacto = useIsMobile()
  const temArea =
    !compacto && serie != null && campo != null && serie.length > 0
  return (
    <Kpi
      label={label}
      // Valor sempre neutro e forte: o sinal +/− carrega o sentido, nunca só a cor (a11y).
      valor={
        <>
          <Valor
            centavos={centavos}
            sinal={sinal}
            oculto={oculto}
            neutro
            className="font-semibold whitespace-nowrap"
          />
          {delta != null ? <Delta delta={delta} titulo={tituloDelta} /> : null}
        </>
      }
      detalhe={rodape}
    >
      {temArea && serie && campo ? (
        <AreaTendencia buckets={serie} campo={campo} oculto={oculto} />
      ) : null}
    </Kpi>
  )
}

/** Saldo em contas do dashboard: o herói com o olho que liga o modo privacidade de TODOS os
 *  cards do painel (o estado mora na página). */
export function SaldoDestaque({
  centavos,
  contas,
  oculto,
  onAlternarOculto,
}: {
  centavos: number
  /** Quantas contas (BANK) somam o saldo; omitido enquanto carrega. */
  contas?: number
  oculto: boolean
  onAlternarOculto: () => void
}) {
  return (
    <CardDestaque
      titulo="Saldo em contas"
      centavos={centavos}
      oculto={oculto}
      onAlternarOculto={onAlternarOculto}
      rodape={
        contas != null
          ? contas === 1
            ? "1 conta"
            : `${contas} contas`
          : undefined
      }
    />
  )
}
