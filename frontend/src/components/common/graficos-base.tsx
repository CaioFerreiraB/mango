import { useMemo } from "react"

import { EChart } from "@/components/common/echart"
import {
  comAlfa,
  escaparHTML,
  linhaTooltipHTML,
  opcoesBase,
  useCores,
  useTemaGrafico,
  type EChartsOption,
  type TemaGrafico,
} from "@/lib/echart-tema"

// Peças genéricas de gráfico (ECharts) com a forma de dados que as telas já usavam no recharts:
// linhas de objetos + chave do eixo X + séries com cor em expressão CSS (`var(--primary)`).

const semMovimento = () =>
  typeof window !== "undefined" &&
  window.matchMedia?.("(prefers-reduced-motion: reduce)").matches

type Linha = Record<string, unknown>

function eixoX(
  t: TemaGrafico,
  rotulos: string[],
  formatar?: (v: string) => string,
  colado = false
): EChartsOption["xAxis"] {
  return {
    type: "category",
    data: rotulos,
    boundaryGap: !colado,
    axisTick: { show: false },
    axisLine: { lineStyle: { color: t.borda } },
    axisLabel: {
      color: t.textoSec,
      hideOverlap: true,
      formatter: formatar ? (v: string) => formatar(v) : undefined,
      // Série diária com rótulo mensal: só o 1º dia de cada rótulo aparece (sem "ago ago ago").
      interval: formatar
        ? (i: number) =>
            i === 0 || formatar(rotulos[i]) !== formatar(rotulos[i - 1])
        : "auto",
    },
  }
}

function eixoY(t: TemaGrafico, formatar: (v: number) => string) {
  return {
    type: "value" as const,
    scale: true,
    axisLabel: { color: t.textoSec, formatter: (v: number) => formatar(v) },
    splitLine: { lineStyle: { color: t.borda } },
  }
}

/** Tooltip de eixo com cabeçalho formatado e uma linha por série (nulos somem). */
function tooltipEixo(
  t: TemaGrafico,
  rotulos: string[],
  formatarRotulo: (v: string) => string,
  formatarValor: (v: number) => string,
  ponteiro: "line" | "shadow",
  /** HTML extra no fim do tooltip do ponto `i` (ex.: total, diferença). */
  detalhe?: (i: number) => string
): EChartsOption["tooltip"] {
  return {
    ...opcoesBase(t).tooltip,
    trigger: "axis",
    axisPointer:
      ponteiro === "line"
        ? { type: "line", lineStyle: { color: t.borda } }
        : { type: "shadow" },
    formatter: (params) => {
      const ps = Array.isArray(params) ? params : [params]
      const i = ps[0]?.dataIndex ?? 0
      const linhas = ps
        .filter((p) => p.value != null && p.value !== "")
        .map((p) =>
          linhaTooltipHTML(
            String(p.color),
            String(p.seriesName),
            formatarValor(Number(p.value))
          )
        )
      const extra = detalhe?.(i)
      // O rótulo pode ser nome do usuário (ex.: categoria): escapado. `detalhe` é HTML deliberado.
      return `<div style="margin-bottom:4px;font-weight:500">${escaparHTML(formatarRotulo(rotulos[i] ?? ""))}</div>${linhas.join("")}${extra ? `<div style="margin-top:6px">${extra}</div>` : ""}`
    },
  }
}

const num = (v: unknown) =>
  typeof v === "number" && Number.isFinite(v) ? v : null

export type SerieLinha = {
  chave: string
  nome: string
  /** Expressão CSS de cor (ex.: `var(--primary)`). */
  cor: string
  tracejada?: boolean
  largura?: number
  /** Marca cada ponto (série mensal curta). */
  pontos?: boolean
  /** Liga os buracos (série com datas esparsas, ex.: indicador sem pregão). */
  conectarNulos?: boolean
}

/** Linhas sobre um eixo X categórico (datas/meses), todas na mesma escala (um eixo só). */
export function GraficoLinhas({
  dados,
  x,
  series,
  formatarX,
  formatarRotulo = (v) => v,
  formatarY,
  formatarValor = formatarY,
  legenda = false,
  referenciaX,
  detalheTooltip,
  altura = 240,
  ariaLabel,
}: {
  dados: Linha[]
  x: string
  series: SerieLinha[]
  detalheTooltip?: (i: number) => string
  formatarX?: (v: string) => string
  formatarRotulo?: (v: string) => string
  formatarY: (v: number) => string
  formatarValor?: (v: number) => string
  legenda?: boolean
  /** Linha vertical de referência num valor do eixo X (ex.: fim do trecho estimado). */
  referenciaX?: { valor: string; rotulo: string }
  altura?: number
  ariaLabel: string
}) {
  const t = useTemaGrafico()
  const cores = useCores(series.map((s) => s.cor))
  const option = useMemo<EChartsOption>(() => {
    const rotulos = dados.map((d) => String(d[x] ?? ""))
    return {
      ...opcoesBase(t),
      animation: !semMovimento(),
      grid: {
        left: 4,
        right: 12,
        top: 16,
        bottom: legenda ? 32 : 4,
        outerBoundsMode: "same",
        outerBoundsContain: "axisLabel",
      },
      xAxis: eixoX(t, rotulos, formatarX, true),
      yAxis: eixoY(t, formatarY),
      tooltip: tooltipEixo(
        t,
        rotulos,
        formatarRotulo,
        formatarValor,
        "line",
        detalheTooltip
      ),
      legend: legenda
        ? {
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
          }
        : undefined,
      series: series.map((s, i) => ({
        name: s.nome,
        type: "line" as const,
        data: dados.map((d) => num(d[s.chave])),
        showSymbol: !!s.pontos,
        connectNulls: !!s.conectarNulos,
        // Suave sem inventar valor: a monotônica não passa acima/abaixo dos pontos vizinhos.
        smooth: 0.35,
        smoothMonotone: "x" as const,
        symbol: "circle",
        symbolSize: s.pontos ? 6 : 8,
        lineStyle: {
          color: cores[i],
          width: s.largura ?? 2,
          type: s.tracejada ? [4, 3] : ("solid" as const),
        },
        itemStyle: { color: cores[i] },
        ...(i === 0 && referenciaX
          ? {
              markLine: {
                symbol: "none",
                silent: true,
                lineStyle: { color: t.textoSec, type: [2, 4], width: 1 },
                label: {
                  formatter: referenciaX.rotulo,
                  position: "insideEndTop" as const,
                  color: t.textoSec,
                  fontSize: 10,
                },
                data: [{ xAxis: referenciaX.valor }],
              },
            }
          : {}),
      })),
    }
  }, [
    dados,
    x,
    series,
    cores,
    formatarX,
    formatarRotulo,
    formatarY,
    formatarValor,
    legenda,
    referenciaX,
    detalheTooltip,
    t,
  ])
  return (
    <EChart
      option={option}
      ariaLabel={ariaLabel}
      className="w-full"
      altura={altura}
    />
  )
}

/** Barras de uma série só (ex.: total por mês), ponta arredondada, largura proporcional ao período. */
export function GraficoBarras({
  dados,
  x,
  chave,
  nome,
  cor = "var(--primary)",
  formatarX,
  formatarRotulo = (v) => v,
  formatarY,
  formatarValor = formatarY,
  cores,
  detalheTooltip,
  onClique,
  altura = 240,
  ariaLabel,
}: {
  dados: Linha[]
  x: string
  chave: string
  nome: string
  cor?: string
  /** Cor por barra (expressão CSS; `null` = a cor da série) — ex.: destacar máximo/mínimo. */
  cores?: (string | null)[]
  detalheTooltip?: (i: number) => string
  onClique?: (i: number) => void
  formatarX?: (v: string) => string
  formatarRotulo?: (v: string) => string
  formatarY: (v: number) => string
  formatarValor?: (v: number) => string
  altura?: number
  ariaLabel: string
}) {
  const t = useTemaGrafico()
  // Estável entre renders (useCores memoriza pela chave): a option não pode mudar a cada render.
  const resolvidas = useCores([cor, ...(cores ?? []).map((c) => c ?? cor)])
  const clicavel = onClique != null
  const option = useMemo<EChartsOption>(() => {
    const [corResolvida, ...porBarra] = resolvidas
    const rotulos = dados.map((d) => String(d[x] ?? ""))
    return {
      ...opcoesBase(t),
      animation: !semMovimento(),
      grid: {
        left: 4,
        right: 8,
        top: 12,
        bottom: 4,
        outerBoundsMode: "same",
        outerBoundsContain: "axisLabel",
      },
      xAxis: eixoX(t, rotulos, formatarX),
      yAxis: { ...eixoY(t, formatarY), scale: false },
      tooltip: tooltipEixo(
        t,
        rotulos,
        formatarRotulo,
        formatarValor,
        "shadow",
        detalheTooltip
      ),
      series: [
        {
          name: nome,
          type: "bar",
          cursor: clicavel ? "pointer" : "default",
          data: dados.map((d, i) =>
            porBarra[i]
              ? { value: num(d[chave]), itemStyle: { color: porBarra[i] } }
              : num(d[chave])
          ),
          barMaxWidth: 96,
          barCategoryGap: "30%",
          itemStyle: { color: corResolvida, borderRadius: [4, 4, 0, 0] },
        },
      ],
    }
  }, [
    dados,
    x,
    chave,
    nome,
    resolvidas,
    formatarX,
    formatarRotulo,
    formatarY,
    formatarValor,
    detalheTooltip,
    clicavel,
    t,
  ])
  return (
    <EChart
      option={option}
      ariaLabel={ariaLabel}
      className="w-full"
      altura={altura}
      onClique={onClique ? ({ dataIndex }) => onClique(dataIndex) : undefined}
    />
  )
}

export type SerieBarra = { chave: string; nome: string; cor: string }

/**
 * Colunas agrupadas (2–3 séries lado a lado por período/categoria), mesmo eixo, com legenda.
 * `destaque` repinta as barras de uma série quando a condição vale (ex.: gasto acima do orçado).
 * `empilhada` empilha as séries numa coluna só (partes de um total, ex.: aportado + rendimento).
 */
export function GraficoBarrasAgrupadas({
  dados,
  x,
  series,
  destaque,
  empilhada = false,
  formatarX,
  formatarRotulo = (v) => v,
  formatarY,
  formatarValor = formatarY,
  detalheTooltip,
  onClique,
  altura = 260,
  ariaLabel,
}: {
  dados: Linha[]
  x: string
  series: SerieBarra[]
  destaque?: { serie: number; cor: string; quando: (i: number) => boolean }
  empilhada?: boolean
  formatarX?: (v: string) => string
  formatarRotulo?: (v: string) => string
  formatarY: (v: number) => string
  formatarValor?: (v: number) => string
  detalheTooltip?: (i: number) => string
  onClique?: (i: number) => void
  altura?: number
  ariaLabel: string
}) {
  const t = useTemaGrafico()
  const cores = useCores([...series.map((s) => s.cor), destaque?.cor ?? ""])
  const clicavel = onClique != null
  const option = useMemo<EChartsOption>(() => {
    const rotulos = dados.map((d) => String(d[x] ?? ""))
    const corDestaque = cores[series.length]
    return {
      ...opcoesBase(t),
      animation: !semMovimento(),
      grid: {
        left: 4,
        right: 8,
        top: 12,
        bottom: 32,
        outerBoundsMode: "same",
        outerBoundsContain: "axisLabel",
      },
      xAxis: eixoX(t, rotulos, formatarX),
      yAxis: { ...eixoY(t, formatarY), scale: false },
      tooltip: tooltipEixo(
        t,
        rotulos,
        formatarRotulo,
        formatarValor,
        "shadow",
        detalheTooltip
      ),
      legend: {
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
      },
      series: series.map((s, k) => ({
        name: s.nome,
        type: "bar" as const,
        cursor: clicavel ? "pointer" : "default",
        barMaxWidth: 40,
        barGap: "12%",
        barCategoryGap: "32%",
        // "all": a parte negativa (ex.: rendimento < 0) desconta do topo da pilha, em vez de
        // descer a partir do zero (o padrão "samesign" mostraria o aportado inteiro).
        ...(empilhada ? { stack: "total", stackStrategy: "all" as const } : {}),
        itemStyle: {
          color: cores[k],
          // Empilhada: só o topo da pilha arredonda (cantos internos retos).
          borderRadius:
            !empilhada || k === series.length - 1 ? [4, 4, 0, 0] : 0,
        },
        data: dados.map((d, i) =>
          destaque?.serie === k && destaque.quando(i)
            ? { value: num(d[s.chave]), itemStyle: { color: corDestaque } }
            : num(d[s.chave])
        ),
      })),
    }
  }, [
    dados,
    x,
    series,
    destaque,
    empilhada,
    cores,
    formatarX,
    formatarRotulo,
    formatarY,
    formatarValor,
    detalheTooltip,
    clicavel,
    t,
  ])
  return (
    <EChart
      option={option}
      ariaLabel={ariaLabel}
      className="w-full"
      altura={altura}
      onClique={onClique ? ({ dataIndex }) => onClique(dataIndex) : undefined}
    />
  )
}

export type FatiaRosca = { nome: string; valor: number; cor: string }

/** Rosca sem legenda (quem usa põe a legenda/valor ao lado ou no miolo). */
export function Rosca({
  fatias,
  tamanho,
  espessura = 0.24,
  formatarValor,
  ariaLabel,
}: {
  fatias: FatiaRosca[]
  tamanho: number
  /** Fração do raio ocupada pelo anel. */
  espessura?: number
  /** Sem formatador → sem tooltip (ex.: anel de progresso, o miolo já diz o valor). */
  formatarValor?: (v: number) => string
  ariaLabel: string
}) {
  const t = useTemaGrafico()
  const cores = useCores(fatias.map((f) => f.cor))
  const option = useMemo<EChartsOption>(() => {
    const total = fatias.reduce((s, f) => s + f.valor, 0)
    return {
      ...opcoesBase(t),
      animation: false,
      tooltip: formatarValor
        ? {
            ...opcoesBase(t).tooltip,
            trigger: "item",
            formatter: (p) => {
              const item = Array.isArray(p) ? p[0] : p
              const v = Number(item.value)
              const pct =
                total > 0 ? ` · ${Math.round((v / total) * 100)}%` : ""
              return linhaTooltipHTML(
                String(item.color),
                String(item.name),
                formatarValor(v) + pct
              )
            },
          }
        : { show: false },
      series: [
        {
          type: "pie",
          radius: [`${Math.round((1 - espessura) * 97)}%`, "97%"],
          startAngle: 90,
          silent: !formatarValor,
          label: { show: false },
          labelLine: { show: false },
          itemStyle: {
            borderColor: t.superficie,
            borderWidth: fatias.length > 1 ? 2 : 0,
          },
          emphasis: { scale: false },
          data: fatias.map((f, i) => ({
            name: f.nome,
            value: f.valor,
            itemStyle: { color: cores[i] },
          })),
        },
      ],
    }
  }, [fatias, cores, espessura, formatarValor, t])
  return (
    <EChart
      option={option}
      ariaLabel={ariaLabel}
      className="shrink-0"
      altura={tamanho}
      largura={tamanho}
    />
  )
}

/** Área compacta sem eixos (tendência): linha na cor primária + degradê que some. */
export function Sparkline({
  dados,
  nome,
  formatarRotulo = (v) => v,
  formatarValor,
  altura = 64,
  ariaLabel,
  cor,
}: {
  dados: { rotulo: string; valor: number }[]
  nome: string
  formatarRotulo?: (v: string) => string
  formatarValor: (v: number) => string
  altura?: number
  ariaLabel: string
  /** Cor da linha/área (ex.: branco sobre a faixa de marca); padrão = destaque do tema. */
  cor?: string
}) {
  const t = useTemaGrafico()
  const option = useMemo<EChartsOption>(() => {
    const c = cor ?? t.primary
    const rotulos = dados.map((d) => d.rotulo)
    return {
      ...opcoesBase(t),
      animation: !semMovimento(),
      grid: { left: 0, right: 0, top: 4, bottom: 0 },
      xAxis: { ...eixoX(t, rotulos, undefined, true), show: false },
      // Folga embaixo (60% da amplitude): a curva fica no terço de cima, como tendência — sem
      // os "vales" até o chão que faziam a variação parecer dramática.
      yAxis: {
        type: "value",
        show: false,
        min: (v: { min: number; max: number }) => v.min - (v.max - v.min) * 0.6,
        max: (v: { min: number; max: number }) => v.max + (v.max - v.min) * 0.1,
      },
      tooltip: tooltipEixo(t, rotulos, formatarRotulo, formatarValor, "line"),
      series: [
        {
          name: nome,
          type: "line",
          data: dados.map((d) => d.valor),
          smooth: 0.4,
          smoothMonotone: "x",
          showSymbol: false,
          lineStyle: { color: c, width: 1.75 },
          itemStyle: { color: c },
          areaStyle: {
            color: {
              type: "linear",
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: comAlfa(c, cor ? 0.28 : 0.16) },
                { offset: 1, color: comAlfa(c, 0) },
              ],
            },
          },
        },
      ],
    }
  }, [dados, nome, formatarRotulo, formatarValor, t, cor])
  return (
    <EChart
      option={option}
      ariaLabel={ariaLabel}
      className="w-full"
      altura={altura}
    />
  )
}
