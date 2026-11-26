import type { ECharts } from "echarts/core"
import { useMemo, useRef, useState, type ComponentProps } from "react"

import { eixoBRL } from "@/components/dashboard/chart-helpers"
import { EChart } from "@/components/common/echart"
import { Sparkline } from "@/components/common/graficos-base"
import {
  comAlfa,
  linhaTooltipHTML,
  opcoesBase,
  useTemaGrafico,
  type EChartsOption,
  type TemaGrafico,
} from "@/lib/echart-tema"
import type {
  Granularidade,
  PatrimonioPonto,
  SerieBucket,
} from "@/lib/api/dashboard"
import {
  distribuirCategorias,
  ehCategoriaReal,
  ID_OUTRAS,
  type Distribuicao,
  type GastoEntrada,
} from "@/lib/categorias-grafico"
import { formatBRL, formatBucketLabel } from "@/lib/format"
import { cn } from "@/lib/utils"

const semMovimento = () =>
  typeof window !== "undefined" &&
  window.matchMedia?.("(prefers-reduced-motion: reduce)").matches

const corSlot = (t: TemaGrafico, slot: number | null) =>
  slot === null ? t.outras : t.cat[slot]

/** Eixos cartesianos do sistema: grid hairline sólido e recessivo, ticks em BRL compacto. */
function eixos(t: TemaGrafico, rotulos: string[]): EChartsOption {
  return {
    grid: {
      left: 4,
      right: 8,
      top: 12,
      bottom: 4,
      outerBoundsMode: "same",
      outerBoundsContain: "axisLabel",
    },
    xAxis: {
      type: "category",
      data: rotulos,
      axisTick: { show: false },
      axisLine: { lineStyle: { color: t.borda } },
      axisLabel: { color: t.textoSec, hideOverlap: true },
    },
    yAxis: {
      type: "value",
      axisLabel: {
        color: t.textoSec,
        formatter: (v: number) => eixoBRL(v),
      },
      splitLine: { lineStyle: { color: t.borda, type: "solid" } },
    },
  }
}

/** Tooltip de eixo: cabeçalho do período + uma linha por série com valor ≠ 0 (+ total, opcional). */
function tooltipEixo(
  formatar: (v: number) => string = formatBRL,
  comTotal = false
): EChartsOption["tooltip"] {
  return {
    trigger: "axis",
    axisPointer: { type: "shadow" },
    formatter: (params) => {
      const ps = Array.isArray(params) ? params : [params]
      const linhas = ps
        .filter((p) => Number(p.value) !== 0)
        .map((p) =>
          linhaTooltipHTML(
            String(p.color),
            String(p.seriesName),
            formatar(Number(p.value))
          )
        )
      const total = ps.reduce((acc, p) => acc + Number(p.value || 0), 0)
      const rodape =
        comTotal && linhas.length > 1
          ? `<div style="margin-top:6px;font-weight:500">Total ${formatar(total)}</div>`
          : ""
      return `<div style="margin-bottom:4px;font-weight:500">${ps[0]?.name ?? ""}</div>${linhas.join("") || "Sem movimento"}${rodape}`
    },
  }
}

// Legenda numa linha só (rola com setas quando não cabe): quebrar em 2+ linhas invadiria o plot.
const legenda = (t: TemaGrafico): EChartsOption["legend"] => ({
  type: "scroll",
  pageIconColor: t.textoSec,
  pageIconInactiveColor: t.borda,
  pageTextStyle: { color: t.textoSec },
  bottom: 0,
  icon: "roundRect",
  itemWidth: 10,
  itemHeight: 10,
  itemGap: 16,
  textStyle: { color: t.textoSec },
})

// --- Entradas e saídas (+ resultado tracejado) -------------------------------------------------

/**
 * Barras agrupadas entradas × saídas por período e o resultado como linha tracejada, neutra e
 * apagada, no mesmo eixo (mesma grandeza em R$ — nada de 2º eixo).
 */
export function GraficoFluxo({
  buckets,
  granularidade,
}: {
  buckets: SerieBucket[]
  granularidade: Granularidade
}) {
  const t = useTemaGrafico()
  const option = useMemo<EChartsOption>(() => {
    const rotulos = buckets.map((b) =>
      formatBucketLabel(b.inicio, granularidade)
    )
    const barra = (nome: string, cor: string, dados: number[]) => ({
      name: nome,
      type: "bar" as const,
      data: dados,
      // Largura proporcional ao espaço do período (dia < semana < mês); teto só p/ 1-2 buckets.
      barMaxWidth: 72,
      barGap: "10%",
      barCategoryGap: "30%",
      itemStyle: { color: cor, borderRadius: [4, 4, 0, 0] },
    })
    return {
      ...opcoesBase(t),
      animation: !semMovimento(),
      ...eixos(t, rotulos),
      grid: {
        left: 4,
        right: 8,
        top: 12,
        bottom: 32,
        outerBoundsMode: "same",
        outerBoundsContain: "axisLabel",
      },
      tooltip: { ...opcoesBase(t).tooltip, ...tooltipEixo() },
      legend: legenda(t),
      series: [
        barra(
          "Entradas",
          t.positivo,
          buckets.map((b) => b.entradas_centavos)
        ),
        barra(
          "Saídas",
          t.negativo,
          buckets.map((b) => b.saidas_centavos)
        ),
        {
          name: "Resultado",
          type: "line",
          data: buckets.map((b) => b.resultado_centavos),
          smooth: 0.35,
          smoothMonotone: "x",
          symbol: "circle",
          symbolSize: 6,
          showSymbol: false,
          z: 3,
          // Tinta neutra, não o accent: com o accent azul, a linha e a legenda ficavam da mesma
          // cor das barras de Entradas (--positive é azul).
          lineStyle: {
            color: t.texto,
            width: 2,
            type: [6, 4],
            opacity: 0.75,
          },
          itemStyle: {
            color: t.texto,
            borderColor: t.superficie,
            borderWidth: 2,
          },
        },
      ],
    }
  }, [buckets, granularidade, t])
  return (
    <EChart
      option={option}
      altura={280}
      ariaLabel="Entradas e saídas por período, com o resultado"
    />
  )
}

// --- Mini-área de tendência (cards do topo) ----------------------------------------------------

export type CampoSerie =
  | "entradas_centavos"
  | "saidas_centavos"
  | "resultado_centavos"
  | "investido_centavos"

const NOME_CAMPO: Record<CampoSerie, string> = {
  entradas_centavos: "Entradas",
  saidas_centavos: "Saídas",
  resultado_centavos: "Resultado",
  investido_centavos: "Investido",
}

/**
 * Tendência de um campo da série nos últimos meses, como área compacta (sparkline). Linha na cor
 * primária + degradê que some — único acento (DESIGN.md "Restrained"). Vazio → `null`.
 */
/** Modo privacidade: o tooltip mostra a máscara no lugar do valor (estável p/ o memo da option). */
const mascarar = () => "R$ ••••"

export function AreaTendencia({
  buckets,
  campo,
  oculto = false,
}: {
  buckets: SerieBucket[]
  campo: CampoSerie
  oculto?: boolean
}) {
  const dados = useMemo(
    () =>
      buckets.map((b) => ({
        rotulo: formatBucketLabel(b.inicio, "mensal"),
        valor: b[campo],
      })),
    [buckets, campo]
  )
  if (buckets.length === 0) return null
  return (
    <Sparkline
      dados={dados}
      altura={48}
      nome={NOME_CAMPO[campo]}
      formatarValor={oculto ? mascarar : formatBRL}
      ariaLabel={`Tendência de ${NOME_CAMPO[campo].toLowerCase()} nos últimos meses`}
    />
  )
}

// --- Roscas ------------------------------------------------------------------------------------

type Fatia = { nome: string; valor: number; cor: string }

function opcaoRosca(t: TemaGrafico, fatias: Fatia[]): EChartsOption {
  const total = fatias.reduce((s, f) => s + f.valor, 0)
  return {
    ...opcoesBase(t),
    animation: !semMovimento(),
    tooltip: {
      ...opcoesBase(t).tooltip,
      trigger: "item",
      formatter: (p) => {
        const item = Array.isArray(p) ? p[0] : p
        const v = Number(item.value)
        const pct = total > 0 ? ` · ${Math.round((v / total) * 100)}%` : ""
        return linhaTooltipHTML(
          String(item.color),
          String(item.name),
          formatBRL(v) + pct
        )
      },
    },
    series: [
      {
        type: "pie",
        radius: ["62%", "92%"],
        avoidLabelOverlap: false,
        label: { show: false },
        labelLine: { show: false },
        // Gap de 2px na cor da superfície entre fatias (dataviz), não um traço.
        itemStyle: {
          borderColor: t.superficie,
          borderWidth: 2,
          borderRadius: 3,
        },
        emphasis: { scale: true, scaleSize: 4 },
        data: fatias.map((f) => ({
          name: f.nome,
          value: f.valor,
          itemStyle: { color: f.cor },
        })),
      },
    ],
  }
}

function SemDados() {
  return (
    <p className="py-8 text-center text-sm text-muted-foreground">
      Sem dados no período.
    </p>
  )
}

// --- Despesas por categoria: rosca + barras-legenda ---------------------------------------------

/**
 * Rosca (todas as despesas do período; 9ª+ categoria dobra em "Outras") sem legenda própria, e ao
 * lado barras horizontais — uma por categoria, todas — que servem de legenda: mesma cor do
 * segmento, valor e %. Hover numa realça a outra. Totais do período inteiro (não dos buckets).
 */
/** Categoria escolhida num gráfico (clique) — abre as transações dela no período. */
export type CategoriaSelecionada = { id: string; nome: string }

export function DistribuicaoCategorias({
  gastos,
  rotulo,
  onSelecionar,
  ariaLabel = "Distribuição das despesas por categoria no período",
  rotuloLista = "Despesas por categoria",
  detalhe,
}: {
  gastos: GastoEntrada[]
  rotulo: Map<string, string>
  onSelecionar?: (c: CategoriaSelecionada) => void
  ariaLabel?: string
  rotuloLista?: string
  /** Linha secundária por item (ex.: quebra por conta de um meio de pagamento). */
  detalhe?: Map<string, string>
}) {
  const t = useTemaGrafico()
  const dist = useMemo(
    () => distribuirCategorias(gastos, rotulo),
    [gastos, rotulo]
  )
  const [ativa, setAtiva] = useState<number | null>(null) // índice da fatia
  const chart = useRef<ECharts | null>(null)
  const fatias = useMemo(
    () => dist.fatias.map((f) => ({ ...f, cor: corSlot(t, f.slot) })),
    [dist, t]
  )
  const option = useMemo(() => opcaoRosca(t, fatias), [t, fatias])

  if (dist.itens.length === 0) return <SemDados />

  const fatiaDoItem = (slot: number | null) =>
    slot === null ? fatias.length - 1 : slot
  function realcar(idx: number | null) {
    const c = chart.current
    if (c) {
      c.dispatchAction({ type: "downplay", seriesIndex: 0 })
      if (idx !== null)
        c.dispatchAction({ type: "highlight", seriesIndex: 0, dataIndex: idx })
    }
    setAtiva(idx)
  }
  const max = dist.itens[0].valor

  return (
    <div className="grid items-center gap-6 @2xl:grid-cols-[minmax(180px,260px)_1fr]">
      <div className="relative mx-auto aspect-square w-full max-w-[260px]">
        <EChart
          option={option}
          className="size-full"
          ariaLabel={ariaLabel}
          instancia={(c) => (chart.current = c)}
          onHover={setAtiva}
          onClique={({ dataIndex }) => {
            const f = fatias[dataIndex]
            if (f && ehCategoriaReal(f.id)) onSelecionar?.(f)
          }}
        />
        {/* Total no miolo: pointer-events-none para não roubar o hover da rosca. */}
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-xs text-muted-foreground">Total</span>
          {/* Líquido (= KPI): compras menos estorno de categoria sem compra no período. */}
          <span className="text-lg font-semibold tabular-nums">
            {formatBRL(dist.total + dist.abatimento)}
          </span>
        </div>
      </div>
      <BarrasLegenda
        dist={dist}
        t={t}
        max={max}
        ativa={ativa}
        fatiaDoItem={fatiaDoItem}
        onHover={realcar}
        onSelecionar={onSelecionar}
        rotuloLista={rotuloLista}
        detalhe={detalhe}
      />
    </div>
  )
}

/** `<button>` quando clicável, senão `<div>` — mesmo visual, sem botão morto no tab. */
function LinhaLegenda({
  onClick,
  ...props
}: Omit<ComponentProps<"div">, "onClick"> & { onClick?: () => void }) {
  if (!onClick) return <div {...props} />
  return (
    <button
      type="button"
      onClick={onClick}
      {...(props as ComponentProps<"button">)}
      className={cn(
        props.className,
        "cursor-pointer hover:bg-muted/60 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
      )}
    />
  )
}

function BarrasLegenda({
  dist,
  t,
  max,
  ativa,
  fatiaDoItem,
  onHover,
  onSelecionar,
  rotuloLista,
  detalhe,
}: {
  dist: Distribuicao
  t: TemaGrafico
  max: number
  ativa: number | null
  fatiaDoItem: (slot: number | null) => number
  onHover: (idx: number | null) => void
  onSelecionar?: (c: CategoriaSelecionada) => void
  rotuloLista: string
  detalhe?: Map<string, string>
}) {
  return (
    <ul
      className="scrollbar-sutil max-h-[300px] space-y-1 overflow-y-auto pr-1"
      aria-label={rotuloLista}
      onMouseLeave={() => onHover(null)}
    >
      {dist.itens.map((it) => {
        const idx = fatiaDoItem(it.slot)
        const apagada = ativa !== null && ativa !== idx
        return (
          <li key={it.id} onMouseEnter={() => onHover(idx)}>
            {/* Categoria real vira botão (abre as transações); "Outras"/"Sem categoria" não. */}
            <LinhaLegenda
              className={cn(
                "block w-full rounded-md px-2 py-1.5 text-left transition-opacity duration-150",
                apagada && "opacity-45",
                ativa === idx && "bg-muted/60"
              )}
              onClick={
                onSelecionar && ehCategoriaReal(it.id)
                  ? () => onSelecionar(it)
                  : undefined
              }
              onFocus={() => onHover(idx)}
              onBlur={() => onHover(null)}
            >
              <div className="flex items-baseline justify-between gap-3 text-sm">
                <span className="truncate">{it.nome}</span>
                <span className="shrink-0 tabular-nums">
                  {formatBRL(it.valor)}
                  <span className="ml-1.5 text-xs text-muted-foreground">
                    {Math.round((it.valor / dist.total) * 100)}%
                  </span>
                </span>
              </div>
              <div className="mt-1 h-1.5 rounded-full bg-muted" aria-hidden>
                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${Math.max((it.valor / max) * 100, 1)}%`,
                    background: corSlot(t, it.slot),
                  }}
                />
              </div>
              {detalhe?.get(it.id) ? (
                <p className="mt-1 truncate text-xs text-muted-foreground">
                  {detalhe.get(it.id)}
                </p>
              ) : null}
            </LinhaLegenda>
          </li>
        )
      })}
      {dist.abatimento < 0 ? (
        <li className="flex items-baseline justify-between gap-3 px-2 py-1.5 text-sm text-muted-foreground">
          <span className="truncate">Estornos sem compra no período</span>
          <span className="shrink-0 tabular-nums">
            {formatBRL(dist.abatimento)}
          </span>
        </li>
      ) : null}
    </ul>
  )
}

/** Barras empilhadas: cada barra é um período, categorias nas mesmas cores da distribuição. */
export function BarrasEmpilhadasCategorias({
  buckets,
  granularidade,
  rotulo,
  comLegenda = true,
  onSelecionar,
}: {
  buckets: SerieBucket[]
  granularidade: Granularidade
  rotulo: Map<string, string>
  /** No dashboard as barras-legenda acima já identificam as cores. */
  comLegenda?: boolean
  onSelecionar?: (c: CategoriaSelecionada) => void
}) {
  const t = useTemaGrafico()
  const dist = useMemo(
    () =>
      distribuirCategorias(
        buckets.flatMap((b) => b.por_categoria),
        rotulo
      ),
    [buckets, rotulo]
  )
  // Séries do empilhado: as fatias da rosca + "Outras" para tudo que ficou fora delas — inclusive
  // categoria de soma ≤ 0 (estorno, ajuste negativo de fatura), que a rosca descarta mas a barra
  // precisa somar para fechar no total do período.
  const fatiasPilha = useMemo(() => {
    const temResto = buckets.some((b) =>
      b.por_categoria.some(
        (g) => g.total_centavos !== 0 && dist.slotDe(g.categoria_id) === null
      )
    )
    return temResto && !dist.fatias.some((f) => f.slot === null)
      ? [
          ...dist.fatias,
          { id: ID_OUTRAS, nome: "Outras", valor: 0, slot: null },
        ]
      : dist.fatias
  }, [buckets, dist])
  const option = useMemo<EChartsOption>(() => {
    const series = fatiasPilha.map((f, i) => {
      const valores = buckets.map((b) =>
        b.por_categoria
          .filter((g) => dist.slotDe(g.categoria_id) === f.slot)
          .reduce((s, g) => s + g.total_centavos, 0)
      )
      const topo = i === fatiasPilha.length - 1
      return {
        name: f.nome,
        type: "bar" as const,
        stack: "cat",
        data: valores,
        barMaxWidth: 96,
        barCategoryGap: "30%",
        itemStyle: {
          color: corSlot(t, f.slot),
          // Gap de 2px entre segmentos (dataviz); só o topo da pilha é arredondado.
          borderColor: t.superficie,
          borderWidth: 1,
          borderRadius: topo ? [4, 4, 0, 0] : 0,
        },
      }
    })
    return {
      ...opcoesBase(t),
      animation: !semMovimento(),
      ...eixos(
        t,
        buckets.map((b) => formatBucketLabel(b.inicio, granularidade))
      ),
      ...(comLegenda
        ? {
            legend: legenda(t),
            grid: {
              left: 4,
              right: 8,
              top: 12,
              bottom: 32,
              outerBoundsMode: "same",
              outerBoundsContain: "axisLabel",
            },
          }
        : {}),
      tooltip: { ...opcoesBase(t).tooltip, ...tooltipEixo(formatBRL, true) },
      series,
    }
  }, [buckets, granularidade, dist, fatiasPilha, comLegenda, t])
  return (
    <EChart
      option={option}
      altura={comLegenda ? 280 : 240}
      ariaLabel="Despesas por categoria em cada período"
      onClique={({ seriesIndex }) => {
        const f = fatiasPilha[seriesIndex]
        if (f && ehCategoriaReal(f.id)) onSelecionar?.(f)
      }}
    />
  )
}

// --- Evolução patrimonial -----------------------------------------------------------------------

/**
 * Patrimônio total (contas + investimentos brutos) e líquido (descontado IR/IOF), mês a mês.
 * Trecho do líquido estimado (snapshot antigo sem líquido) sai tracejado; mês antes do 1º
 * snapshot da carteira avisa no tooltip que só há contas.
 */
export function GraficoPatrimonio({ pontos }: { pontos: PatrimonioPonto[] }) {
  const t = useTemaGrafico()
  const option = useMemo<EChartsOption>(() => {
    const rotulos = pontos.map((p) =>
      formatBucketLabel(`${p.mes}-01`, "mensal")
    )
    const est = pontos.map((p) => p.liquido_estimado)
    // Duas séries p/ o líquido: real (sólida) e estimada (tracejada), ligadas no ponto de troca.
    const liqReal = pontos.map((p, i) => (est[i] ? null : p.liquido_centavos))
    const liqEst = pontos.map((p, i) =>
      // Liga o trecho tracejado aos vizinhos reais nas duas pontas (entrada e saída).
      est[i] || est[i - 1] || est[i + 1] ? p.liquido_centavos : null
    )
    const COR_TOTAL = t.cat[0]
    const COR_LIQ = t.cat[2]
    const linha = (
      nome: string,
      cor: string,
      dados: (number | null)[],
      tracejada = false
    ) => ({
      name: nome,
      type: "line" as const,
      data: dados,
      smooth: 0.35,
      smoothMonotone: "x" as const,
      symbol: "circle",
      symbolSize: 8,
      showSymbol: false,
      lineStyle: {
        color: cor,
        width: 2,
        type: tracejada ? [6, 4] : ("solid" as const),
      },
      itemStyle: { color: cor, borderColor: t.superficie, borderWidth: 2 },
    })
    return {
      ...opcoesBase(t),
      animation: !semMovimento(),
      ...eixos(t, rotulos),
      grid: {
        left: 4,
        right: 8,
        top: 12,
        bottom: 32,
        outerBoundsMode: "same",
        outerBoundsContain: "axisLabel",
      },
      yAxis: {
        type: "value",
        scale: true,
        axisLabel: { color: t.textoSec, formatter: (v: number) => eixoBRL(v) },
        splitLine: { lineStyle: { color: t.borda } },
      },
      legend: {
        ...legenda(t),
        data: ["Patrimônio total", "Patrimônio líquido"],
      },
      tooltip: {
        ...opcoesBase(t).tooltip,
        trigger: "axis",
        axisPointer: { type: "line", lineStyle: { color: t.borda } },
        formatter: (params) => {
          const i = (Array.isArray(params) ? params[0] : params).dataIndex ?? 0
          const p = pontos[i]
          const nota = !p.tem_investimentos
            ? "Sem dados de investimento neste mês (só contas)"
            : p.liquido_estimado
              ? "Líquido estimado (IR/IOF da posição atual)"
              : ""
          return (
            `<div style="margin-bottom:4px;font-weight:500">${rotulos[i]}</div>` +
            linhaTooltipHTML(
              COR_TOTAL,
              "Patrimônio total",
              formatBRL(p.total_centavos)
            ) +
            linhaTooltipHTML(
              COR_LIQ,
              `Patrimônio líquido${p.liquido_estimado ? " (estimado)" : ""}`,
              formatBRL(p.liquido_centavos)
            ) +
            `<div style="margin-top:6px;opacity:.7">Contas ${formatBRL(p.contas_centavos)} · Investimentos ${formatBRL(p.investimentos_centavos)}</div>` +
            (nota ? `<div style="margin-top:2px;opacity:.7">${nota}</div>` : "")
          )
        },
      },
      series: [
        {
          ...linha(
            "Patrimônio total",
            COR_TOTAL,
            pontos.map((p) => p.total_centavos)
          ),
          areaStyle: { color: comAlfa(COR_TOTAL, 0.08) },
        },
        linha("Patrimônio líquido", COR_LIQ, liqReal),
        linha("Patrimônio líquido", COR_LIQ, liqEst, true),
      ],
    }
  }, [pontos, t])
  if (pontos.length === 0) return <SemDados />
  return (
    <EChart
      option={option}
      altura={280}
      ariaLabel="Evolução do patrimônio total e líquido, mês a mês"
    />
  )
}
