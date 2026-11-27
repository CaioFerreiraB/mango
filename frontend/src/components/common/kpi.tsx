import { Eye, EyeOff } from "lucide-react"
import type { CSSProperties, ReactNode } from "react"

import { CenaMascote, Relevo } from "@/components/common/mascote-cena"
import { Valor } from "@/components/common/valor"
import { Card } from "@/components/ui/card"
import { formatBRL } from "@/lib/format"
import type { Cena } from "@/lib/illustrations"
import { cn } from "@/lib/utils"

/** Grade de KPIs do app inteiro: quantos couberem por linha, cada um com pelo menos 11rem (ou a
 *  largura toda no celular estreito). Item de grid com `min-w-0` para não estourar a coluna. */
export const GRADE_KPI =
  "grid gap-3 md:gap-4 grid-cols-[repeat(auto-fit,minmax(min(100%,11rem),1fr))]"

/**
 * KPI — o mesmo cartão de número em todas as telas (DESIGN.md §Superfícies): rótulo pequeno em
 * cinza médio, valor forte e tabular, detalhe opcional e, em `children`, um visual que sangra até
 * a borda inferior (mini-área). Mede o próprio espaço: estreito reduz o valor em vez de cortá-lo.
 */
export function Kpi({
  label,
  valor,
  detalhe,
  acao,
  children,
  className,
}: {
  label: ReactNode
  valor: ReactNode
  /** Linha de contexto sob o valor (ex.: "Total aportado", delta vs CDI). */
  detalhe?: ReactNode
  /** Controle no canto do rótulo (ex.: tooltip de ajuda). */
  acao?: ReactNode
  /** Visual em sangria no rodapé (sparkline/mini-área). */
  children?: ReactNode
  className?: string
}) {
  return (
    <Card
      className={cn("@container min-w-0 gap-0 overflow-hidden py-0", className)}
    >
      <div
        className={cn("px-4 pt-4 @[13rem]:px-5", children ? "pb-2" : "pb-4")}
      >
        <div className="flex min-h-5 items-start gap-2">
          <p className="min-w-0 flex-1 text-[0.8125rem] leading-tight font-medium text-muted-foreground">
            {label}
          </p>
          {acao}
        </div>
        <div className="mt-2 flex flex-wrap items-baseline gap-x-2 gap-y-1 text-lg leading-none font-bold tracking-[-0.025em] tabular-nums @[10.5rem]:text-xl @[13rem]:text-[1.5rem]">
          {valor}
        </div>
        {detalhe ? (
          <div className="mt-2 text-xs text-muted-foreground">{detalhe}</div>
        ) : null}
      </div>
      {children ? <div className="mt-auto">{children}</div> : null}
    </Card>
  )
}

/**
 * Herói da página — **no máximo um por tela** (`data-destaque` deixa isso testável). No estilo
 * Mercury: card branco como os outros, o número-âncora grande e tabular, uma linha de contexto e,
 * opcionalmente, um gráfico em sangria no rodapé (`grafico`) e o mascote do módulo no canto.
 * A ênfase vem de tamanho e espaço — não de bloco colorido.
 */
export function CardDestaque({
  titulo,
  centavos,
  valor,
  oculto = false,
  onAlternarOculto,
  rodape,
  mascote,
  arte,
  grafico,
  estatisticas,
  children,
  className,
}: {
  titulo: string
  /** Valor em dinheiro; para outra grandeza (ex.: "1 de 2 pagas") use `valor`. */
  centavos?: number
  valor?: ReactNode
  oculto?: boolean
  /** Olho do modo privacidade; omitido, o card só respeita o `oculto` de fora. */
  onAlternarOculto?: () => void
  /** Linha de contexto sob o valor (ex.: "2 contas", variação). */
  rodape?: ReactNode
  /** Cena do mascote do módulo (em cena no canto inferior direito; some em card estreito). */
  mascote?: Cena
  /** No lugar do mascote: uma peça do próprio assunto (ex.: o cartão tombado na fatura), no mesmo
   *  canto e com a mesma regra de sumir em card estreito. */
  arte?: ReactNode
  /** Gráfico que sangra até a borda inferior do card. */
  grafico?: ReactNode
  /** Números de apoio NA linha do herói (ex.: orçado · gasto) — no lugar de KPIs soltos ao lado. */
  estatisticas?: { rotulo: string; valor: ReactNode }[]
  /** Conteúdo extra sob o valor (ex.: barra do mês). */
  children?: ReactNode
  className?: string
}) {
  return (
    <Card
      data-destaque
      className={cn(
        "@container relative isolate min-w-0 gap-0 overflow-hidden rounded-[1.75rem] py-0",
        arte && "group",
        (mascote || arte) && "@xl:min-h-56",
        className
      )}
    >
      {mascote ? (
        // Mascote em cena no canto (só em card largo o bastante para não encostar nos dados).
        <div className="hidden @xl:contents">
          <CenaMascote cena={mascote} tamanho="medio" />
        </div>
      ) : arte ? (
        // Arte no lugar do mascote: mesmo relevo atrás, entra subindo como ele e, como o card na
        // lista de Contas e cartões, se endireita um pouco sob o cursor (group-hover na arte).
        <div className="hidden @xl:contents">
          <Relevo />
          <div
            aria-hidden
            className="pointer-events-none absolute top-9 right-16 z-[6] entra"
            style={
              {
                "--dist": "40px",
                "--atraso": "80ms",
                "--dur": "620ms",
              } as CSSProperties
            }
          >
            <div className="origin-top scale-[1.35]">{arte}</div>
          </div>
        </div>
      ) : null}
      <div
        className={cn(
          "relative z-10 px-5 pt-5 md:px-7 md:pt-7",
          grafico ? "pb-2" : "pb-5 md:pb-7",
          (mascote || arte) && "@xl:pr-64"
        )}
      >
        <div className="flex min-h-8 items-start justify-between gap-3">
          <p className="truncate pt-1 text-sm font-medium text-muted-foreground">
            {titulo}
          </p>
          {onAlternarOculto ? (
            <BotaoOcultar
              oculto={oculto}
              onClick={onAlternarOculto}
              className="-mt-0.5 -mr-1.5 size-8 text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:ring-ring"
            />
          ) : null}
        </div>
        {/* Número indivisível: o tamanho é o menor entre o degrau da faixa e o que cabe na largura
            útil do card — (100cqi − padding − reserva do mascote) ÷ a largura do texto em em
            (~0,6em por caractere, mínimo 9em = "R$ 1.234.567,89"). A reserva só existe a partir
            de @xl, quando o mascote aparece. */}
        <div
          style={
            {
              "--ems":
                centavos != null && valor == null
                  ? Math.max(9, formatBRL(centavos).length * 0.6)
                  : 9,
            } as CSSProperties
          }
          className={cn(
            "mt-2 text-[min(2.25rem,calc((100cqi-var(--reserva))/var(--ems)))] leading-none font-extrabold tracking-[-0.04em] whitespace-nowrap tabular-nums [--reserva:3.5rem] @md:text-[min(2.75rem,calc((100cqi-var(--reserva))/var(--ems)))] @3xl:text-[min(3.25rem,calc((100cqi-var(--reserva))/var(--ems)))]",
            (mascote || arte) && "@xl:[--reserva:19.5rem]"
          )}
        >
          {valor ??
            (centavos != null ? (
              <Valor
                centavos={centavos}
                oculto={oculto}
                neutro
                animado
                className="font-extrabold"
              />
            ) : null)}
        </div>
        {rodape != null ? (
          <div className="mt-3 flex flex-wrap items-center gap-x-1.5 gap-y-1 text-sm text-muted-foreground">
            {rodape}
          </div>
        ) : null}
        {estatisticas?.length ? (
          <dl className="mt-5 flex flex-wrap gap-x-8 gap-y-3">
            {estatisticas.map((e) => (
              <div key={e.rotulo} className="min-w-0">
                <dt className="text-xs font-semibold text-muted-foreground">
                  {e.rotulo}
                </dt>
                <dd className="mt-0.5 text-base font-bold tracking-tight whitespace-nowrap tabular-nums">
                  {e.valor}
                </dd>
              </div>
            ))}
          </dl>
        ) : null}
        {children ? <div className="mt-5">{children}</div> : null}
      </div>
      {grafico ? <div className="mt-auto">{grafico}</div> : null}
    </Card>
  )
}

/** Olho do modo privacidade: mascara os valores de todos os cards da página. */
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
        "flex shrink-0 items-center justify-center rounded-full transition-[background-color,color,transform] duration-150 ease-out focus-visible:ring-2 focus-visible:outline-none active:scale-95 motion-reduce:transition-none motion-reduce:active:scale-100",
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
