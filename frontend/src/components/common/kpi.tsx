import { Eye, EyeOff } from "lucide-react"
import type { ReactNode } from "react"

import { Mascote } from "@/components/common/mascote"
import { Valor } from "@/components/common/valor"
import { Card, CardContent } from "@/components/ui/card"
import type { Cena } from "@/lib/illustrations"
import { cn } from "@/lib/utils"

/** Grade de KPIs do app inteiro: quantos couberem por linha, cada um com pelo menos 10rem (ou a
 *  largura toda no celular estreito). Item de grid com `min-w-0` para não estourar a coluna. */
export const GRADE_KPI =
  "grid gap-3 md:gap-4 grid-cols-[repeat(auto-fit,minmax(min(100%,10rem),1fr))]"

/**
 * KPI — o mesmo cartão de número em todas as telas (DESIGN.md §Anatomia de página): rótulo,
 * valor (forte, `tabular-nums`), detalhe opcional e, em `children`, um visual que sangra até a
 * borda inferior (mini-área do painel). Mede o próprio espaço: estreito reduz o valor em vez de
 * cortá-lo — número cortado é número ambíguo.
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
      className={cn(
        "@container min-w-0 gap-0 py-4",
        children ? "overflow-hidden pb-0" : null,
        className
      )}
    >
      <CardContent className="space-y-1 px-4 @[13rem]:px-5">
        <div className="flex min-h-5 items-start gap-2">
          <p className="min-w-0 flex-1 text-sm leading-tight text-muted-foreground">
            {label}
          </p>
          {acao}
        </div>
        <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1 text-lg font-semibold tracking-tight tabular-nums @[12rem]:text-xl">
          {valor}
        </div>
        {detalhe ? (
          <div className="text-xs text-muted-foreground">{detalhe}</div>
        ) : null}
      </CardContent>
      {children ? <div className="mt-3">{children}</div> : null}
    </Card>
  )
}

/**
 * Herói da página — **no máximo um por tela** (`data-destaque` deixa isso testável). Degradê
 * escuro do accent (`--destaque-a → b`, texto branco AA em qualquer preset e tema) com ondas
 * decorativas e, opcionalmente, o mascote do módulo em sangria no canto. Ordem de camadas:
 * ondas → mascote → dados (dados sempre por cima). Mede o próprio espaço (`@container`).
 */
export function CardDestaque({
  titulo,
  centavos,
  valor,
  oculto = false,
  onAlternarOculto,
  rodape,
  mascote,
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
  /** Pílula no rodapé (ex.: "3 contas"). */
  rodape?: ReactNode
  /** Cena do mascote do módulo (≤ 8rem, some em card estreito). */
  mascote?: Cena
  /** Conteúdo extra sob o valor (ex.: barra do mês). */
  children?: ReactNode
  className?: string
}) {
  return (
    <div
      data-destaque
      className={cn(
        "@container relative isolate flex flex-col overflow-hidden rounded-xl bg-destaque-b bg-linear-135 from-destaque-a to-destaque-b px-5 pt-4 pb-5 text-white shadow-[0_12px_28px_-14px_var(--destaque-b)]",
        className
      )}
    >
      {/* Ondas: decoração pura, atrás de tudo. */}
      <svg
        viewBox="0 0 320 120"
        preserveAspectRatio="none"
        className="pointer-events-none absolute inset-x-0 bottom-0 -z-20 h-3/4 w-full text-white"
        aria-hidden
      >
        <path
          d="M0 96 C 60 92, 110 70, 170 74 S 270 40, 320 18 V120 H0 Z"
          fill="currentColor"
          fillOpacity={0.07}
        />
        <path
          d="M0 112 C 80 108, 130 92, 200 94 S 290 66, 320 54 V120 H0 Z"
          fill="currentColor"
          fillOpacity={0.08}
        />
      </svg>
      {mascote ? (
        <Mascote
          cena={mascote}
          className={cn(
            "absolute bottom-0 -z-10 hidden h-[calc(100%-0.75rem)] max-h-32 w-auto object-bottom @sm:block",
            // Com o olho no canto, o mascote recua para não disputar o alvo de toque.
            onAlternarOculto ? "right-16" : "right-4"
          )}
        />
      ) : null}
      <div
        className={cn(
          "flex min-h-9 items-start justify-between gap-3",
          mascote && !onAlternarOculto && "@sm:pr-28"
        )}
      >
        <p className="truncate pt-1 text-sm text-white/80">{titulo}</p>
        {onAlternarOculto ? (
          <BotaoOcultar
            oculto={oculto}
            onClick={onAlternarOculto}
            className="-mr-1 size-9 bg-white/12 text-white hover:bg-white/20 focus-visible:ring-white/70"
          />
        ) : null}
      </div>
      <div className="mt-1 text-2xl leading-tight font-bold tracking-tight whitespace-nowrap text-white tabular-nums @[17rem]:text-[1.875rem]">
        {valor ??
          (centavos != null ? (
            <Valor centavos={centavos} oculto={oculto} neutro />
          ) : null)}
      </div>
      {children ? (
        <div className={cn("mt-3", mascote && "@sm:pr-28")}>{children}</div>
      ) : null}
      {rodape != null ? (
        // mt-auto: esticado até a altura dos vizinhos, a pílula desce ao rodapé.
        <div className="mt-auto self-start pt-3">
          <span className="inline-flex flex-wrap items-center gap-x-1 rounded-full bg-white/12 px-2.5 py-1 text-xs text-white/90">
            {rodape}
          </span>
        </div>
      ) : null}
    </div>
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
        "flex shrink-0 items-center justify-center rounded-full transition-[background-color,transform] duration-150 ease-out focus-visible:ring-2 focus-visible:outline-none active:scale-95 motion-reduce:transition-none motion-reduce:active:scale-100",
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
