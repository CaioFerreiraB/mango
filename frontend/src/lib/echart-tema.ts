import { BarChart, LineChart, PieChart } from "echarts/charts"
import type {
  BarSeriesOption,
  LineSeriesOption,
  PieSeriesOption,
} from "echarts/charts"
import {
  AriaComponent,
  GridComponent,
  LegendComponent,
  TooltipComponent,
} from "echarts/components"
import type {
  AriaComponentOption,
  GridComponentOption,
  LegendComponentOption,
  TooltipComponentOption,
} from "echarts/components"
import * as echarts from "echarts/core"
import { SVGRenderer } from "echarts/renderers"
import { useMemo, useSyncExternalStore } from "react"

// Import modular: só os gráficos/componentes usados entram no bundle.
echarts.use([
  BarChart,
  LineChart,
  PieChart,
  AriaComponent,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  SVGRenderer,
])

export { echarts }

export type EChartsOption = echarts.ComposeOption<
  | BarSeriesOption
  | LineSeriesOption
  | PieSeriesOption
  | AriaComponentOption
  | GridComponentOption
  | LegendComponentOption
  | TooltipComponentOption
>

/** Escapa texto que entra no HTML do tooltip (nomes de categoria são do usuário). */
export const escaparHTML = echarts.format.encodeHTML

// --- Tokens do tema resolvidos --------------------------------------------------------------
// O SVG/canvas do ECharts não lê `var(--x)` e o parser de cor dele não entende oklch: cada token
// é resolvido para rgba pintando 1px num canvas. Accent (data-accent) e tema (.dark) mudam no
// <html> → um MutationObserver invalida a versão e os gráficos re-renderizam.

let versao = 0
function assinarTema(avisar: () => void) {
  const obs = new MutationObserver(() => {
    versao++
    avisar()
  })
  obs.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["class", "data-accent", "style"],
  })
  return () => obs.disconnect()
}

function resolverCores(nomes: readonly string[]): string[] {
  const probe = document.createElement("span")
  probe.style.display = "none"
  document.body.appendChild(probe)
  const ctx = document.createElement("canvas").getContext("2d", {
    willReadFrequently: true,
  })
  const cores = nomes.map((nome) => {
    probe.style.color = `var(${nome})`
    const css = getComputedStyle(probe).color
    if (!ctx) return css
    ctx.clearRect(0, 0, 1, 1)
    ctx.fillStyle = css
    ctx.fillRect(0, 0, 1, 1)
    const [r, g, b, a] = ctx.getImageData(0, 0, 1, 1).data
    return `rgba(${r},${g},${b},${+(a / 255).toFixed(3)})`
  })
  probe.remove()
  return cores
}

const TOKENS = [
  "--foreground",
  "--muted-foreground",
  "--border",
  "--card",
  "--popover",
  "--popover-foreground",
  "--primary",
  "--positive",
  "--negative",
  "--chart-cat-outras",
  ...Array.from({ length: 8 }, (_, i) => `--chart-cat-${i + 1}`),
] as const

export type TemaGrafico = {
  texto: string
  textoSec: string
  borda: string
  superficie: string
  popover: string
  popoverTexto: string
  primary: string
  positivo: string
  negativo: string
  outras: string
  /** Paleta categórica validada (8 slots, ordem fixa, nunca ciclada — dataviz). */
  cat: string[]
  fonte: string
}

/** Cores e fonte do tema atual, prontas para o ECharts; muda com tema e accent. */
export function useTemaGrafico(): TemaGrafico {
  const v = useSyncExternalStore(assinarTema, () => versao)
  return useMemo(() => {
    void v // dependência: re-resolve quando o tema/accent muda
    const c = resolverCores(TOKENS)
    return {
      texto: c[0],
      textoSec: c[1],
      borda: c[2],
      superficie: c[3],
      popover: c[4],
      popoverTexto: c[5],
      primary: c[6],
      positivo: c[7],
      negativo: c[8],
      outras: c[9],
      cat: c.slice(10),
      fonte: getComputedStyle(document.body).fontFamily,
    }
  }, [v])
}

/** Base comum: fonte/texto do tema, tooltip no visual do popover, aria ligado. */
export function opcoesBase(t: TemaGrafico): EChartsOption {
  return {
    aria: { enabled: true },
    animationDuration: 250,
    textStyle: { fontFamily: t.fonte, color: t.textoSec },
    tooltip: {
      backgroundColor: t.popover,
      borderColor: t.borda,
      borderWidth: 1,
      padding: [8, 10],
      textStyle: { color: t.popoverTexto, fontFamily: t.fonte, fontSize: 12 },
      extraCssText:
        "border-radius:8px;box-shadow:0 4px 16px rgb(0 0 0 / 0.08);",
      confine: true,
    },
  }
}

/** Uma linha de tooltip: marcador da cor + nome (texto escapado) + valor alinhado à direita. */
export function linhaTooltipHTML(cor: string, nome: string, valor: string) {
  return (
    `<div style="display:flex;align-items:center;gap:8px;min-width:160px">` +
    `<span style="width:10px;height:10px;border-radius:2px;background:${cor};flex:none"></span>` +
    `<span style="opacity:.75">${escaparHTML(nome)}</span>` +
    `<span style="margin-left:auto;font-variant-numeric:tabular-nums;font-weight:500">${escaparHTML(valor)}</span>` +
    `</div>`
  )
}
