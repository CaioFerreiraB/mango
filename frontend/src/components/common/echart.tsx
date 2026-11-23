import { useEffect, useRef } from "react"

import { echarts, type EChartsOption } from "@/lib/echart-tema"
import { cn } from "@/lib/utils"

/**
 * Wrapper único do ECharts: init (SVG), `setOption` sem merge a cada `option` nova, resize
 * por ResizeObserver e dispose. `onHover` devolve o `dataIndex` sob o cursor (ou null);
 * `onClique`, o item clicado.
 */
export function EChart({
  option,
  className,
  ariaLabel,
  onHover,
  onClique,
  instancia,
  altura,
  largura,
}: {
  option: EChartsOption
  className?: string
  ariaLabel?: string
  /** px; alternativa a uma classe de altura (tamanhos vindos de props). */
  altura?: number
  largura?: number
  onHover?: (dataIndex: number | null) => void
  /** Clique num item (fatia, barra/segmento): índices do dado e da série. */
  onClique?: (p: { dataIndex: number; seriesIndex: number }) => void
  /** Recebe a instância (para `dispatchAction` vindo de fora, ex.: legenda HTML). */
  instancia?: (chart: echarts.ECharts | null) => void
}) {
  const ref = useRef<HTMLDivElement>(null)
  const chartRef = useRef<echarts.ECharts | null>(null)
  const onHoverRef = useRef(onHover)
  const onCliqueRef = useRef(onClique)
  const instanciaRef = useRef(instancia)
  useEffect(() => {
    onHoverRef.current = onHover
    onCliqueRef.current = onClique
    instanciaRef.current = instancia
  })

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const chart = echarts.init(el, null, { renderer: "svg" })
    chartRef.current = chart
    chart.on("mouseover", (p) => onHoverRef.current?.(p.dataIndex ?? null))
    chart.on("mouseout", () => onHoverRef.current?.(null))
    chart.on("click", (p) =>
      onCliqueRef.current?.({
        dataIndex: p.dataIndex ?? 0,
        seriesIndex: p.seriesIndex ?? 0,
      })
    )
    instanciaRef.current?.(chart)
    const ro = new ResizeObserver(() => chart.resize())
    ro.observe(el)
    return () => {
      ro.disconnect()
      instanciaRef.current?.(null)
      chart.dispose()
      chartRef.current = null
    }
  }, [])

  useEffect(() => {
    chartRef.current?.setOption(option, { notMerge: true })
  }, [option])

  return (
    <div
      ref={ref}
      // @container = contenção de largura: o SVG (largura em px do último resize) não vira largura
      // mínima dos ancestrais; sem isso, um grid que precisa encolher (ex.: chat abrindo) não
      // encolhe, o ResizeObserver nunca dispara e o gráfico vaza.
      className={cn("@container w-full", className)}
      style={{ height: altura, width: largura }}
      role="img"
      aria-label={ariaLabel}
    />
  )
}
