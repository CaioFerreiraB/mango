import { useEffect, useRef } from "react"

import { useMovimentoReduzido } from "@/hooks/use-movimento-reduzido"
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

  // Preferência de movimento reduzido observada ao vivo (mudar com o gráfico aberto desliga a
  // animação já no próximo setOption) — vale para todo gráfico, sem cada um assinar.
  const reduzido = useMovimentoReduzido()
  useEffect(() => {
    chartRef.current?.setOption(
      {
        ...option,
        ...(reduzido ? { animation: false } : {}),
        // O ECharts troca o aria-label do contêiner por uma descrição gerada com os valores
        // brutos das séries; fixar a descrição mantém o rótulo dado (e não vaza valor oculto).
        ...(ariaLabel
          ? { aria: { enabled: true, label: { description: ariaLabel } } }
          : {}),
      },
      { notMerge: true }
    )
  }, [option, reduzido, ariaLabel])

  return (
    <div
      ref={ref}
      // @container = contenção de largura: o SVG (largura em px do último resize) não vira largura
      // mínima dos ancestrais; sem isso, um grid que precisa encolher (ex.: chat abrindo) não
      // encolhe, o ResizeObserver nunca dispara e o gráfico vaza.
      className={cn("@container w-full", className)}
      // minHeight = altura: crescendo num contêiner flexível (card mais alto), volta a encolher
      // até a altura pedida — sem ela, o SVG já renderizado seguraria o tamanho maior.
      style={{ height: altura, minHeight: altura, width: largura }}
      role="img"
      aria-label={ariaLabel}
    />
  )
}
