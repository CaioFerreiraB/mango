import { ArrowDownRight, ArrowUpRight } from "lucide-react"
import { useMemo, type ReactNode } from "react"

import { Sparkline } from "@/components/common/graficos-base"
import { CardDestaque, Kpi } from "@/components/common/kpi"
import { Valor } from "@/components/common/valor"
import { AreaTendencia, type CampoSerie } from "@/components/dashboard/graficos"
import { useIsMobile } from "@/hooks/use-mobile"
import type { SerieBucket } from "@/lib/api/dashboard"
import { formatBRL, formatDate } from "@/lib/format"

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
            animado
            className="font-bold whitespace-nowrap"
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

/** Saldo em contas do dashboard: o herói (estilo Mercury) com o saldo somado das contas nos
 *  últimos 30 dias em sangria e a variação no período; o olho liga o modo privacidade de TODOS os
 *  cards do painel (o estado mora na página). */
export function SaldoDestaque({
  centavos,
  contas,
  pontos,
  oculto,
  onAlternarOculto,
  className,
}: {
  className?: string
  centavos: number
  /** Quantas contas (BANK) somam o saldo; omitido enquanto carrega. */
  contas?: number
  /** Saldo diário somado das contas (ordem cronológica). */
  pontos?: { data: string; saldo_centavos: number }[]
  oculto: boolean
  onAlternarOculto?: () => void
}) {
  const dados = useMemo(
    () =>
      (pontos ?? []).map((p) => ({ rotulo: p.data, valor: p.saldo_centavos })),
    [pontos]
  )
  const variacao =
    dados.length >= 2 ? dados[dados.length - 1].valor - dados[0].valor : null
  return (
    <CardDestaque
      className={className}
      titulo="Saldo em contas"
      centavos={centavos}
      oculto={oculto}
      onAlternarOculto={onAlternarOculto}
      mascote="money"
      rodape={
        <>
          {variacao != null && variacao !== 0 ? (
            <>
              <Valor centavos={variacao} sinal oculto={oculto} />
              <span>nos últimos 30 dias</span>
              <span aria-hidden>·</span>
            </>
          ) : null}
          {contas != null ? (
            <span>{contas === 1 ? "1 conta" : `${contas} contas`}</span>
          ) : null}
        </>
      }
      grafico={
        dados.length >= 2 ? (
          <Sparkline
            dados={dados}
            nome="Saldo"
            altura={96}
            formatarRotulo={formatDate}
            formatarValor={oculto ? () => "R$ ••••" : formatBRL}
            ariaLabel="Saldo somado das contas nos últimos 30 dias"
          />
        ) : undefined
      }
    />
  )
}
