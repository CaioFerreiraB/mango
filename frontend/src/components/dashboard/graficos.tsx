import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  XAxis,
  YAxis,
} from "recharts"

import {
  eixoBRL,
  linhaTooltip,
  prepararCategorias,
} from "@/components/dashboard/chart-helpers"
import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart"
import type { Granularidade, SerieBucket } from "@/lib/api/dashboard"
import { formatBRL, formatBucketLabel } from "@/lib/format"

function LegendaValores({
  itens,
}: {
  itens: { nome: string; valor: number; cor: string }[]
}) {
  const total = itens.reduce((s, i) => s + i.valor, 0)
  return (
    <ul className="w-full space-y-1.5 text-sm">
      {itens.map((it) => (
        <li key={it.nome} className="flex items-center justify-between gap-3">
          <span className="flex min-w-0 items-center gap-2">
            <span
              className="size-2.5 shrink-0 rounded-[2px]"
              style={{ background: it.cor }}
              aria-hidden
            />
            <span className="truncate">{it.nome}</span>
          </span>
          <span className="shrink-0 text-muted-foreground tabular-nums">
            {formatBRL(it.valor)}
            {total > 0 ? ` · ${Math.round((it.valor / total) * 100)}%` : ""}
          </span>
        </li>
      ))}
    </ul>
  )
}

// --- Entradas e saídas -------------------------------------------------------------------------

const CFG_FLUXO: ChartConfig = {
  entradas: { label: "Entradas", color: "var(--positive)" },
  saidas: { label: "Saídas", color: "var(--negative)" },
}
const CFG_RESULTADO: ChartConfig = {
  resultado: { label: "Resultado", color: "var(--primary)" },
}

function dadosFluxo(buckets: SerieBucket[], gran: Granularidade) {
  return buckets.map((b) => ({
    label: formatBucketLabel(b.inicio, gran),
    entradas: b.entradas_centavos,
    saidas: b.saidas_centavos,
    resultado: b.resultado_centavos,
  }))
}

/** Barras agrupadas (não empilhadas): entradas vs. saídas por período. */
export function BarrasEntradasSaidas({
  buckets,
  granularidade,
}: {
  buckets: SerieBucket[]
  granularidade: Granularidade
}) {
  const dados = dadosFluxo(buckets, granularidade)
  return (
    <ChartContainer config={CFG_FLUXO} className="aspect-auto h-[240px] w-full">
      <BarChart data={dados} barGap={2}>
        <CartesianGrid vertical={false} strokeDasharray="3 3" />
        <XAxis
          dataKey="label"
          tickLine={false}
          axisLine={false}
          tickMargin={8}
        />
        <YAxis
          tickLine={false}
          axisLine={false}
          width={44}
          tickFormatter={eixoBRL}
        />
        <ChartTooltip
          content={
            <ChartTooltipContent
              formatter={(value, name, item) =>
                linhaTooltip(value, String(name), item.color, CFG_FLUXO)
              }
            />
          }
        />
        <ChartLegend content={<ChartLegendContent />} />
        <Bar dataKey="entradas" fill="var(--color-entradas)" radius={4} />
        <Bar dataKey="saidas" fill="var(--color-saidas)" radius={4} />
      </BarChart>
    </ChartContainer>
  )
}

/** Linha do resultado (entradas − saídas) por período. Série única: sem legenda, o título nomeia. */
export function LinhaResultado({
  buckets,
  granularidade,
}: {
  buckets: SerieBucket[]
  granularidade: Granularidade
}) {
  const dados = dadosFluxo(buckets, granularidade)
  return (
    <ChartContainer
      config={CFG_RESULTADO}
      className="aspect-auto h-[240px] w-full"
    >
      <LineChart data={dados}>
        <CartesianGrid vertical={false} strokeDasharray="3 3" />
        <XAxis
          dataKey="label"
          tickLine={false}
          axisLine={false}
          tickMargin={8}
        />
        <YAxis
          tickLine={false}
          axisLine={false}
          width={44}
          tickFormatter={eixoBRL}
        />
        <ChartTooltip
          content={
            <ChartTooltipContent
              formatter={(value, name, item) =>
                linhaTooltip(value, String(name), item.color, CFG_RESULTADO)
              }
            />
          }
        />
        <Line
          dataKey="resultado"
          type="monotone"
          stroke="var(--color-resultado)"
          strokeWidth={2}
          dot={false}
        />
      </LineChart>
    </ChartContainer>
  )
}

// --- Mini-área de tendência (cards do topo) ----------------------------------------------------

export type CampoSerie =
  "entradas_centavos" | "saidas_centavos" | "resultado_centavos"

const NOME_CAMPO: Record<CampoSerie, string> = {
  entradas_centavos: "Entradas",
  saidas_centavos: "Saídas",
  resultado_centavos: "Resultado",
}

/**
 * Tendência de um campo da série nos últimos meses, como área compacta (sparkline). Linha na cor
 * primária + degradê que some — único acento (DESIGN.md "Restrained"). Vazio → `null` (o card fica
 * só com título+valor até a série chegar).
 */
export function AreaTendencia({
  buckets,
  campo,
}: {
  buckets: SerieBucket[]
  campo: CampoSerie
}) {
  if (buckets.length === 0) return null
  const config: ChartConfig = {
    valor: { label: NOME_CAMPO[campo], color: "var(--primary)" },
  }
  const dados = buckets.map((b) => ({
    label: formatBucketLabel(b.inicio, "mensal"),
    valor: b[campo],
  }))
  const grad = `area-${campo}` // id único por card (campos distintos)
  const semMovimento =
    typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-reduced-motion: reduce)").matches

  return (
    <ChartContainer config={config} className="aspect-auto h-16 w-full">
      <AreaChart data={dados} margin={{ top: 4, right: 0, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id={grad} x1="0" y1="0" x2="0" y2="1">
            <stop
              offset="0%"
              stopColor="var(--color-valor)"
              stopOpacity={0.3}
            />
            <stop
              offset="100%"
              stopColor="var(--color-valor)"
              stopOpacity={0}
            />
          </linearGradient>
        </defs>
        <XAxis dataKey="label" hide />
        <ChartTooltip
          content={
            <ChartTooltipContent
              formatter={(value, name) =>
                linhaTooltip(value, String(name), "var(--color-valor)", config)
              }
            />
          }
        />
        <Area
          dataKey="valor"
          type="monotone"
          stroke="var(--color-valor)"
          strokeWidth={2}
          fill={`url(#${grad})`}
          dot={false}
          isAnimationActive={!semMovimento}
        />
      </AreaChart>
    </ChartContainer>
  )
}

// --- Roscas ------------------------------------------------------------------------------------

function Rosca({
  fatias,
}: {
  fatias: { nome: string; valor: number; cor: string }[]
}) {
  const config: ChartConfig = Object.fromEntries(
    fatias.map((f) => [f.nome, { label: f.nome, color: f.cor }])
  )
  if (fatias.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        Sem dados no período.
      </p>
    )
  }
  return (
    <div className="flex flex-col items-center gap-4 sm:flex-row">
      <ChartContainer config={config} className="aspect-square h-[180px]">
        <PieChart>
          <ChartTooltip
            content={
              <ChartTooltipContent
                hideLabel
                formatter={(value, name, item) =>
                  linhaTooltip(value, String(name), item.payload?.cor, config)
                }
              />
            }
          />
          <Pie
            data={fatias}
            dataKey="valor"
            nameKey="nome"
            innerRadius={50}
            strokeWidth={2}
          >
            {fatias.map((f) => (
              <Cell key={f.nome} fill={f.cor} />
            ))}
          </Pie>
        </PieChart>
      </ChartContainer>
      <div className="w-full sm:flex-1">
        <LegendaValores itens={fatias} />
      </div>
    </div>
  )
}

/** Distribuição entradas vs. saídas do período (§polaridade: cores semânticas). */
export function RoscaEntradasSaidas({
  entradas,
  saidas,
}: {
  entradas: number
  saidas: number
}) {
  const fatias = [
    { nome: "Entradas", valor: entradas, cor: "var(--positive)" },
    { nome: "Saídas", valor: saidas, cor: "var(--negative)" },
  ].filter((f) => f.valor > 0)
  return <Rosca fatias={fatias} />
}

// --- Categorias (rosca + empilhado, redução top-N + "Outros" em chart-helpers) -----------------

/** Rosca da distribuição de gastos por categoria no período. */
export function RoscaCategorias({
  buckets,
  rotulo,
}: {
  buckets: SerieBucket[]
  rotulo: Map<string, string>
}) {
  const { fatias } = prepararCategorias(buckets, rotulo, "semanal")
  return <Rosca fatias={fatias} />
}

/** Barras empilhadas: cada barra é um período, categorias nas cores. */
export function BarrasEmpilhadasCategorias({
  buckets,
  granularidade,
  rotulo,
  n = 5,
}: {
  buckets: SerieBucket[]
  granularidade: Granularidade
  rotulo: Map<string, string>
  n?: number
}) {
  const { config, series, linhas } = prepararCategorias(
    buckets,
    rotulo,
    granularidade,
    n
  )
  return (
    <ChartContainer config={config} className="aspect-auto h-[240px] w-full">
      <BarChart data={linhas}>
        <CartesianGrid vertical={false} strokeDasharray="3 3" />
        <XAxis
          dataKey="label"
          tickLine={false}
          axisLine={false}
          tickMargin={8}
        />
        <YAxis
          tickLine={false}
          axisLine={false}
          width={44}
          tickFormatter={eixoBRL}
        />
        <ChartTooltip
          content={
            <ChartTooltipContent
              formatter={(value, name, item) =>
                linhaTooltip(value, String(name), item.color, config)
              }
            />
          }
        />
        <ChartLegend content={<ChartLegendContent />} />
        {series.map((s, i) => (
          <Bar
            key={s.slug}
            dataKey={s.slug}
            stackId="cat"
            fill={`var(--color-${s.slug})`}
            radius={i === series.length - 1 ? [4, 4, 0, 0] : 0}
          />
        ))}
      </BarChart>
    </ChartContainer>
  )
}
