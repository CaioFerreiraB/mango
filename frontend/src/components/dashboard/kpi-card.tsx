import { ArrowDownRight, ArrowUpRight, Eye, EyeOff } from "lucide-react"
import type { ReactNode } from "react"

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
  // Mobile: card compacto, dois por linha e sem a mini-área (o gráfico nem monta).
  const compacto = useIsMobile()
  const temArea =
    !compacto && serie != null && campo != null && serie.length > 0
  return (
    // Com área: `pb-0` + `overflow-hidden` fazem a área sangrar até a borda inferior arredondada.
    <Card
      className={cn(
        "@container",
        compacto && "gap-0 py-4",
        temArea && "overflow-hidden pb-0"
      )}
    >
      <CardContent
        className={cn("space-y-3", compacto ? "px-4" : "px-4 @[13rem]:px-6")}
      >
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
              // Card estreito (container) reduz o valor em vez de cortá-lo.
              compacto
                ? "text-base @[11rem]:text-lg"
                : "text-base @[11rem]:text-lg @[15rem]:text-2xl"
            )}
          >
            <Valor
              centavos={centavos}
              sinal={sinal}
              oculto={oculto}
              className="font-bold whitespace-nowrap text-foreground"
            />
            {delta != null ? (
              <Delta delta={delta} titulo={tituloDelta} />
            ) : null}
          </div>
          {rodape ? (
            <p className="truncate text-xs text-muted-foreground">{rodape}</p>
          ) : null}
        </div>
        {temArea && serie && campo ? (
          <div className="-mx-4 @[13rem]:-mx-6">
            <AreaTendencia buckets={serie} campo={campo} oculto={oculto} />
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}

/**
 * Saldo em contas: card de destaque no tom escuro do accent do usuário (degradê
 * `--destaque-a → b`, texto branco AA em qualquer preset), ondas decorativas e o olho que liga o
 * modo privacidade de TODOS os cards do painel (o estado mora na página). Mede o próprio espaço
 * (`@container`): no desktop ele ocupa ⅕ da linha, no mobile a linha inteira.
 */
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
    <div className="@container relative isolate flex flex-col overflow-hidden rounded-xl bg-destaque-b bg-linear-135 from-destaque-a to-destaque-b px-5 pt-4 pb-5 text-white shadow-[0_12px_28px_-14px_var(--destaque-b)]">
      {/* Ondas: decoração pura, atrás do conteúdo (dados sempre por cima). */}
      <svg
        viewBox="0 0 320 120"
        preserveAspectRatio="none"
        className="pointer-events-none absolute inset-x-0 bottom-0 -z-10 h-3/4 w-full"
        aria-hidden
      >
        <path
          d="M0 96 C 60 92, 110 70, 170 74 S 270 40, 320 18 V120 H0 Z"
          fill="white"
          fillOpacity="0.07"
        />
        <path
          d="M0 112 C 80 108, 130 92, 200 94 S 290 66, 320 54 V120 H0 Z"
          fill="white"
          fillOpacity="0.08"
        />
      </svg>
      <div className="flex items-start justify-between gap-3">
        <p className="truncate pt-1 text-sm text-white/80">Saldo em contas</p>
        <BotaoOcultar
          oculto={oculto}
          onClick={onAlternarOculto}
          className="-mr-1 size-9 bg-white/12 text-white hover:bg-white/20 focus-visible:ring-white/70"
        />
      </div>
      {/* Estreito (⅕ da linha no desktop) reduz o valor em vez de cortá-lo. */}
      <Valor
        centavos={centavos}
        oculto={oculto}
        neutro
        className="mt-1 block text-2xl leading-tight font-bold tracking-tight whitespace-nowrap text-white @[17rem]:text-[1.875rem]"
      />
      {contas != null ? (
        // mt-auto: no desktop o card estica até a altura dos vizinhos e a pílula desce ao rodapé.
        <p className="mt-auto self-start pt-3">
          <span className="inline-flex rounded-full bg-white/12 px-2.5 py-1 text-xs text-white/90">
            {contas === 1 ? "1 conta" : `${contas} contas`}
          </span>
        </p>
      ) : null}
    </div>
  )
}

/** Olho do modo privacidade: mascara os valores de todos os cards do painel. */
export function BotaoOcultar({
  oculto,
  onClick,
  className,
}: {
  oculto: boolean
  onClick: () => void
  className?: string
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={oculto}
      aria-label="Ocultar valores"
      title={oculto ? "Valores ocultos" : "Ocultar valores"}
      className={cn(
        "flex shrink-0 items-center justify-center rounded-full transition-colors focus-visible:ring-2 focus-visible:outline-none motion-reduce:transition-none",
        className
      )}
    >
      {oculto ? (
        <EyeOff className="size-4" aria-hidden />
      ) : (
        <Eye className="size-4" aria-hidden />
      )}
    </button>
  )
}
