import { useEffect, useRef } from "react"

import { echarts, type EChartsOption } from "@/lib/echart-tema"
import { cn } from "@/lib/utils"

/**
 * Wrapper único do ECharts: init (SVG), `setOption` sem merge a cada `option` nova, resize
 * por ResizeObserver e dispose. `onHover` devolve o `dataIndex` sob o cursor (ou null).
 */
export function EChart({
  option,
  className,
  ariaLabel,
  onHover,
  instancia,
}: {
  option: EChartsOption
  className?: string
  ariaLabel?: string
  onHover?: (dataIndex: number | null) => void
  /** Recebe a instância (para `dispatchAction` vindo de fora, ex.: legenda HTML). */
  instancia?: (chart: echarts.ECharts | null) => void
}) {
  const ref = useRef<HTMLDivElement>(null)
  const chartRef = useRef<echarts.ECharts | null>(null)
  const onHoverRef = useRef(onHover)
  const instanciaRef = useRef(instancia)
  useEffect(() => {
    onHoverRef.current = onHover
    instanciaRef.current = instancia
  })

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const chart = echarts.init(el, null, { renderer: "svg" })
    chartRef.current = chart
    chart.on("mouseover", (p) => onHoverRef.current?.(p.dataIndex ?? null))
    chart.on("mouseout", () => onHoverRef.current?.(null))
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
      className={cn("w-full", className)}
      role="img"
      aria-label={ariaLabel}
    />
  )
}
