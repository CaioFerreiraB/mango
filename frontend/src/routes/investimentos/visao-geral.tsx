import {
  AlertTriangle,
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  CircleCheck,
  CircleDollarSign,
  Coins,
  Eye,
  EyeOff,
  Layers,
  MoreHorizontal,
  Percent,
  Sparkles,
  TrendingUp,
  Wallet,
  X,
} from "lucide-react"
import type { LucideIcon } from "lucide-react"
import { useState, type ReactNode } from "react"
import { Link } from "react-router"
import { Cell, Line, LineChart, Pie, PieChart, XAxis, YAxis } from "recharts"

import { EmptyState } from "@/components/common/empty-state"
import { Valor } from "@/components/common/valor"
import { eixoBRL } from "@/components/dashboard/chart-helpers"
import { SyncButton } from "@/components/sync-button"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart"
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Skeleton } from "@/components/ui/skeleton"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { useContas } from "@/lib/api/contas"
import { useIndicadores, useIndicadoresSerie } from "@/lib/api/indicadores"
import {
  useCarteiraResumo,
  useCarteiraSerie,
  useVisaoGeral,
  type CarteiraAtivoRV,
  type CarteiraItem,
  type CarteiraResumo,
  type VisaoGeralInvestimentos,
} from "@/lib/api/investimentos"
import {
  iconeTipo,
  rotuloSubtype,
  rotuloTipo,
} from "@/lib/investimento-taxonomia"
import {
  formatBRL,
  formatDataISO,
  formatDateTime,
  formatPct,
  hojeISO,
  subMeses,
} from "@/lib/format"
import { cn } from "@/lib/utils"

// Paleta categórica curada (matizes distintos, legíveis em claro/escuro) para o donut por tipo e
// as linhas de indicadores. A rampa --chart-* do tema é monocromática (derivada do accent), então
// aqui usamos hues fixos onde distinguir categorias é o objetivo. Patrimônio segue o --primary.
const PALETA_TIPO = [
  "oklch(0.60 0.13 250)",
  "oklch(0.64 0.15 155)",
  "oklch(0.75 0.14 75)",
  "oklch(0.58 0.19 300)",
  "oklch(0.66 0.16 25)",
  "oklch(0.68 0.12 200)",
]
const COR_OUTROS = "var(--muted-foreground)"
const corTipo = (i: number) => PALETA_TIPO[i] ?? COR_OUTROS

const COR_BENCH: Record<string, string> = {
  cdi: "oklch(0.64 0.15 155)",
  ipca: "oklch(0.75 0.14 75)",
  ibov: "oklch(0.58 0.19 300)",
}

/** Pregão B3 aberto: dia útil (fuso SP), das 10h às 18h. ponytail: sem feriados nacionais. */
function mercadoAberto(): boolean {
  const partes = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/Sao_Paulo",
    weekday: "short",
    hour: "2-digit",
    hour12: false,
  }).formatToParts(new Date())
  const dia = partes.find((p) => p.type === "weekday")?.value
  const hora = Number(partes.find((p) => p.type === "hour")?.value)
  return dia != null && !["Sat", "Sun"].includes(dia) && hora >= 10 && hora < 18
}

export function VisaoGeralPage() {
  const resumo = useCarteiraResumo()
  const vg = useVisaoGeral()
  const contas = useContas()
  const [oculto, setOculto] = useState(false)

  if (resumo.isError) {
    return (
      <EmptyState
        icon={AlertTriangle}
        title="Não foi possível carregar a carteira"
        description="Tente novamente em instantes."
      />
    )
  }

  const totais = resumo.data?.totais
  if (resumo.isSuccess && (totais?.quantidade_ativos ?? 0) === 0) {
    return (
      <EmptyState
        icon={TrendingUp}
        title="Sua carteira de investimentos está vazia"
        description="Conecte uma conta pelo Open Finance para acompanhar patrimônio, rentabilidade e proventos aqui."
      >
        <Button asChild>
          <Link to="/configuracoes">Conectar conta</Link>
        </Button>
      </EmptyState>
    )
  }

  const posicoes = (resumo.data?.grupos ?? []).flatMap((g) => g.itens)
  const total = totais?.valor_centavos ?? 0

  return (
    <div className="space-y-6">
      <Cabecalho atualizadoEm={resumo.dataUpdatedAt} aberto={mercadoAberto()} />

      <Kpis
        resumo={resumo.data}
        vg={vg.data}
        carregando={resumo.isLoading}
        oculto={oculto}
        onToggleOculto={() => setOculto((v) => !v)}
      />

      <div className="grid items-stretch gap-4 lg:grid-cols-3">
        <div className="h-full lg:col-span-2">
          <EvolucaoPatrimonio oculto={oculto} />
        </div>
        <AlocacaoPorTipo
          alocacao={resumo.data?.alocacao ?? []}
          total={total}
          oculto={oculto}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <MaioresMovers
          titulo="Maiores altas"
          ativos={resumo.data?.renda_variavel ?? []}
          tipo="alta"
          oculto={oculto}
        />
        <MaioresMovers
          titulo="Maiores baixas"
          ativos={resumo.data?.renda_variavel ?? []}
          tipo="baixa"
          oculto={oculto}
        />
        <MaioresPosicoes itens={posicoes} total={total} oculto={oculto} />
      </div>

      <InsightsBar
        vg={vg.data}
        numCategorias={resumo.data?.alocacao.length ?? 0}
        contas={contas.data ?? []}
        oculto={oculto}
      />
    </div>
  )
}

// --- cabeçalho ---------------------------------------------------------------------------------

function Cabecalho({
  atualizadoEm,
  aberto,
}: {
  atualizadoEm: number
  aberto: boolean
}) {
  return (
    <header className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold">Visão Geral</h1>
        <p className="text-sm text-muted-foreground">
          Acompanhe o resumo da sua carteira de investimentos.
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <div className="text-right text-xs text-muted-foreground">
          <p>Atualizado em {formatDateTime(atualizadoEm)}</p>
          <p className="inline-flex items-center gap-1.5">
            <span
              className={cn(
                "size-1.5 rounded-full",
                aberto ? "bg-positive" : "bg-muted-foreground"
              )}
              aria-hidden
            />
            Mercado {aberto ? "aberto" : "fechado"}
          </p>
        </div>
        <SyncButton />
      </div>
    </header>
  )
}

// --- KPIs --------------------------------------------------------------------------------------

function KpiCard({
  icon: Icon,
  label,
  valor,
  detalhe,
  acao,
}: {
  icon: LucideIcon
  label: string
  valor: ReactNode
  detalhe?: ReactNode
  acao?: ReactNode
}) {
  return (
    <Card>
      <CardContent className="space-y-2.5">
        <div className="flex items-center gap-2">
          <span
            aria-hidden
            className="grid size-8 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary"
          >
            <Icon className="size-4" />
          </span>
          <p className="min-w-0 flex-1 truncate text-sm text-muted-foreground">
            {label}
          </p>
          {acao}
        </div>
        <div>
          <div className="truncate text-xl font-bold tracking-tight tabular-nums">
            {valor}
          </div>
          {detalhe ? (
            <div className="mt-1 truncate text-xs">{detalhe}</div>
          ) : null}
        </div>
      </CardContent>
    </Card>
  )
}

/** Variação percentual: seta (direção, a11y) + valor absoluto; cor semântica da casa. */
function VarPct({
  pct,
  sufixo,
}: {
  pct: number | null | undefined
  sufixo?: string
}) {
  if (pct == null) return <span className="text-muted-foreground">—</span>
  const sobe = pct >= 0
  const Icone = sobe ? ArrowUpRight : ArrowDownRight
  return (
    <span
      className={cn(
        "inline-flex items-center gap-0.5 font-medium tabular-nums",
        sobe ? "text-positive" : "text-negative"
      )}
    >
      <Icone className="size-3.5" aria-hidden />
      {formatPct(Math.abs(pct))}
      {sufixo ? (
        <span className="font-normal text-muted-foreground"> {sufixo}</span>
      ) : null}
    </span>
  )
}

function Kpis({
  resumo,
  vg,
  carregando,
  oculto,
  onToggleOculto,
}: {
  resumo: CarteiraResumo | undefined
  vg: VisaoGeralInvestimentos | undefined
  carregando: boolean
  oculto: boolean
  onToggleOculto: () => void
}) {
  if (carregando || !resumo) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }, (_, i) => (
          <Skeleton key={i} className="h-24 w-full" />
        ))}
      </div>
    )
  }
  const t = resumo.totais
  const sobe = (t.resultado_centavos ?? 0) >= 0
  const Seta = sobe ? ArrowUpRight : ArrowDownRight
  const nCat = resumo.alocacao.length

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <KpiCard
        icon={Wallet}
        label="Patrimônio total"
        acao={
          <Button
            variant="ghost"
            size="icon-sm"
            className="-mr-1 text-muted-foreground"
            aria-label={oculto ? "Mostrar valores" : "Ocultar valores"}
            aria-pressed={oculto}
            onClick={onToggleOculto}
          >
            {oculto ? (
              <EyeOff className="size-4" />
            ) : (
              <Eye className="size-4" />
            )}
          </Button>
        }
        valor={
          <Valor
            centavos={t.valor_centavos}
            neutro
            oculto={oculto}
            className="text-accent-ink"
          />
        }
        detalhe={
          t.resultado_centavos != null ? (
            <span
              className={cn(
                "inline-flex items-center gap-1 font-medium",
                sobe ? "text-positive" : "text-negative"
              )}
            >
              <Seta className="size-3.5" aria-hidden />
              <Valor
                centavos={t.resultado_centavos}
                sinal
                oculto={oculto}
                className="text-xs"
              />
              {t.resultado_pct != null ? (
                <span className="text-muted-foreground">
                  ({formatPct(t.resultado_pct)})
                </span>
              ) : null}
            </span>
          ) : null
        }
      />
      <KpiCard
        icon={Coins}
        label="Valor investido"
        valor={
          <Valor centavos={t.investido_centavos ?? 0} neutro oculto={oculto} />
        }
        detalhe={<span className="text-muted-foreground">Total aportado</span>}
      />
      <KpiCard
        icon={TrendingUp}
        label="Resultado"
        valor={
          <Valor centavos={t.resultado_centavos ?? 0} neutro oculto={oculto} />
        }
        detalhe={<VarPct pct={t.resultado_pct} />}
      />
      <KpiCard
        icon={Percent}
        label="Rentabilidade (12M)"
        valor={
          vg?.rentabilidade_12m_pct != null ? (
            formatPct(vg.rentabilidade_12m_pct)
          ) : (
            <span className="text-muted-foreground">—</span>
          )
        }
        detalhe={
          vg?.vs_cdi_pp != null ? (
            <VarPct
              pct={vg.vs_cdi_pp}
              sufixo={vg.vs_cdi_pp >= 0 ? "acima do CDI" : "abaixo do CDI"}
            />
          ) : (
            <span className="text-muted-foreground">vs. CDI indisponível</span>
          )
        }
      />
      <KpiCard
        icon={CircleDollarSign}
        label="Dividendos (mês)"
        valor={
          <Valor
            centavos={vg?.dividendos_mes_centavos ?? 0}
            neutro
            oculto={oculto}
          />
        }
        detalhe={
          <span className="text-muted-foreground">Recebidos neste mês</span>
        }
      />
      <KpiCard
        icon={Layers}
        label="Ativos"
        valor={<span className="tabular-nums">{t.quantidade_ativos}</span>}
        detalhe={
          <span className="text-muted-foreground">
            Em {nCat} categoria{nCat === 1 ? "" : "s"}
          </span>
        }
      />
    </div>
  )
}

// --- evolução do patrimônio --------------------------------------------------------------------

const PRESETS = [
  { id: "1m", label: "1M", meses: 1 },
  { id: "3m", label: "3M", meses: 3 },
  { id: "6m", label: "6M", meses: 6 },
  { id: "1a", label: "1A", meses: 12 },
  { id: "5a", label: "5A", meses: 60 },
  { id: "tudo", label: "Tudo", meses: 120 },
]

const MESES_CURTOS = [
  "jan",
  "fev",
  "mar",
  "abr",
  "mai",
  "jun",
  "jul",
  "ago",
  "set",
  "out",
  "nov",
  "dez",
]
const tickMes = (iso: string) => {
  const [ano, mes] = iso.split("-")
  return `${MESES_CURTOS[Number(mes) - 1]}/${ano.slice(2)}`
}

// Séries em R$ (eixo esquerdo) vs. em % de crescimento (eixo direito) — decide o formato do tooltip.
const SERIES_REAIS = new Set(["patrimonio", "investido"])

function linhaEvolucao(
  valor: unknown,
  nome: string,
  cor: string | undefined,
  config: ChartConfig,
  oculto: boolean
) {
  const texto = SERIES_REAIS.has(nome)
    ? oculto
      ? "R$ ••••"
      : formatBRL(Number(valor))
    : formatPct(Number(valor))
  return (
    <>
      <span
        className="mt-0.5 size-2.5 shrink-0 rounded-[2px]"
        style={{ background: cor }}
        aria-hidden
      />
      <div className="flex flex-1 items-center justify-between gap-2 leading-none">
        <span className="text-muted-foreground">
          {config[nome]?.label ?? nome}
        </span>
        <span className="font-mono font-medium text-foreground tabular-nums">
          {texto}
        </span>
      </div>
    </>
  )
}

function EvolucaoPatrimonio({ oculto }: { oculto: boolean }) {
  const [presetId, setPresetId] = useState("1a")
  const [ocultarBench, setOcultarBench] = useState<Set<string>>(new Set())
  const preset = PRESETS.find((p) => p.id === presetId) ?? PRESETS[3]
  const fim = hojeISO()
  const inicio = subMeses(fim, preset.meses)

  const indicadores = useIndicadores()
  const disponiveis = new Set((indicadores.data ?? []).map((i) => i.codigo))
  const benchAll = ["cdi", "ipca", "ibov"].filter((c) => disponiveis.has(c))
  const benchVisiveis = benchAll.filter((c) => !ocultarBench.has(c))

  const serie = useCarteiraSerie({ recorte: "todos", inicio, fim })
  const pontos = serie.data?.pontos ?? []
  const inicioComum = pontos[0]?.data ?? inicio
  const indSerie = useIndicadoresSerie(
    pontos.length >= 2 ? benchVisiveis : [],
    {
      inicio: inicioComum,
      fim,
    }
  )

  // Esquerda (R$): patrimônio e capital investido. Direita (% de crescimento): a própria carteira
  // (indicador do patrimônio) + benchmarks — todos em % acumulado, comparáveis entre si.
  const config: ChartConfig = {
    patrimonio: { label: "Patrimônio", color: "var(--primary)" },
    investido: { label: "Investido", color: "var(--muted-foreground)" },
    carteira: { label: "Carteira", color: "var(--accent-ink)" },
    cdi: { label: "CDI", color: COR_BENCH.cdi },
    ipca: { label: "IPCA", color: COR_BENCH.ipca },
    ibov: { label: "Ibovespa", color: COR_BENCH.ibov },
  }

  const porData = new Map<string, Record<string, number | string>>()
  for (const p of pontos) {
    porData.set(p.data, {
      data: p.data,
      patrimonio: p.valor_centavos,
      investido: p.investido_centavos,
      carteira: p.acumulado_pct,
    })
  }
  for (const s of indSerie.data ?? []) {
    for (const p of s.pontos) {
      const linha = porData.get(p.data)
      if (linha) linha[s.codigo] = p.acumulado_pct
    }
  }
  const dados = [...porData.values()].sort((a, b) =>
    String(a.data).localeCompare(String(b.data))
  )

  return (
    <Card className="h-full">
      <CardHeader className="flex-row flex-wrap items-start justify-between gap-3">
        <div>
          <CardTitle className="text-base">Evolução do patrimônio</CardTitle>
          <CardDescription>
            Valor à esquerda; crescimento vs. mercado à direita
          </CardDescription>
        </div>
        <div className="flex items-center gap-2">
          <ToggleGroup
            type="single"
            size="sm"
            variant="outline"
            spacing={0}
            value={presetId}
            onValueChange={(v) => v && setPresetId(v)}
          >
            {PRESETS.map((p) => (
              <ToggleGroupItem key={p.id} value={p.id}>
                {p.label}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
          {benchAll.length > 0 ? (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="outline"
                  size="icon-sm"
                  aria-label="Escolher indicadores"
                >
                  <MoreHorizontal className="size-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuLabel>Comparar com</DropdownMenuLabel>
                {benchAll.map((c) => (
                  <DropdownMenuCheckboxItem
                    key={c}
                    checked={!ocultarBench.has(c)}
                    onCheckedChange={() =>
                      setOcultarBench((prev) => {
                        const n = new Set(prev)
                        if (n.has(c)) n.delete(c)
                        else n.add(c)
                        return n
                      })
                    }
                  >
                    {config[c]?.label}
                  </DropdownMenuCheckboxItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          ) : null}
        </div>
      </CardHeader>
      <CardContent>
        {serie.isLoading ? (
          <Skeleton className="h-[300px] w-full" />
        ) : pontos.length < 2 ? (
          <p className="py-24 text-center text-sm text-muted-foreground">
            Sem histórico suficiente neste período.
          </p>
        ) : (
          <>
            <ChartContainer
              config={config}
              className="aspect-auto h-[300px] w-full"
            >
              <LineChart data={dados} margin={{ left: 4, right: 8, top: 8 }}>
                <XAxis
                  dataKey="data"
                  tickLine={false}
                  axisLine={false}
                  tickMargin={8}
                  minTickGap={40}
                  tickFormatter={tickMes}
                />
                <YAxis
                  yAxisId="rs"
                  tickLine={false}
                  axisLine={false}
                  width={52}
                  tickFormatter={eixoBRL}
                />
                <YAxis
                  yAxisId="pct"
                  orientation="right"
                  tickLine={false}
                  axisLine={false}
                  width={44}
                  tickFormatter={(v) => `${Math.round(Number(v))}%`}
                />
                <ChartTooltip
                  content={
                    <ChartTooltipContent
                      labelFormatter={(v) => {
                        const s = String(v)
                        return /^\d{4}-\d{2}-\d{2}$/.test(s)
                          ? formatDataISO(s)
                          : s
                      }}
                      formatter={(value, name, item) =>
                        linhaEvolucao(
                          value,
                          String(name),
                          item.color,
                          config,
                          oculto
                        )
                      }
                    />
                  }
                />
                <ChartLegend content={<ChartLegendContent />} />
                <Line
                  yAxisId="rs"
                  dataKey="patrimonio"
                  type="monotone"
                  stroke="var(--color-patrimonio)"
                  strokeWidth={2.5}
                  dot={false}
                />
                <Line
                  yAxisId="rs"
                  dataKey="investido"
                  type="monotone"
                  stroke="var(--color-investido)"
                  strokeWidth={1.5}
                  strokeDasharray="5 4"
                  dot={false}
                />
                <Line
                  yAxisId="pct"
                  dataKey="carteira"
                  type="monotone"
                  stroke="var(--color-carteira)"
                  strokeWidth={2}
                  dot={false}
                />
                {benchVisiveis.map((c) => (
                  <Line
                    key={c}
                    yAxisId="pct"
                    dataKey={c}
                    type="monotone"
                    stroke={`var(--color-${c})`}
                    strokeWidth={1.5}
                    strokeDasharray="4 3"
                    dot={false}
                    connectNulls
                  />
                ))}
              </LineChart>
            </ChartContainer>
            <p className="mt-2 text-center text-xs text-muted-foreground">
              No período de {formatDataISO(inicioComum)} até{" "}
              {formatDataISO(fim)} · crescimento em % acumulado.
            </p>
          </>
        )}
      </CardContent>
    </Card>
  )
}

// --- alocação por tipo de ativo (donut) --------------------------------------------------------

function AlocacaoPorTipo({
  alocacao,
  total,
  oculto,
}: {
  alocacao: CarteiraResumo["alocacao"]
  total: number
  oculto: boolean
}) {
  const fatias = alocacao.map((a, i) => ({
    nome: rotuloSubtype(a.tipo) ?? rotuloTipo(a.tipo),
    valor: a.valor_centavos,
    cor: corTipo(i),
    pct: a.pct,
  }))
  const config: ChartConfig = Object.fromEntries(
    fatias.map((f) => [f.nome, { label: f.nome, color: f.cor }])
  )

  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle className="text-base">Alocação por tipo</CardTitle>
      </CardHeader>
      <CardContent>
        {fatias.length === 0 ? (
          <Skeleton className="h-40 w-full" />
        ) : (
          <div className="space-y-4">
            <div className="relative mx-auto w-fit">
              <ChartContainer
                config={config}
                className="aspect-square h-[180px]"
              >
                <PieChart>
                  <ChartTooltip
                    content={
                      <ChartTooltipContent
                        hideLabel
                        formatter={(value, name, item) => (
                          <>
                            <span
                              className="mt-0.5 size-2.5 shrink-0 rounded-[2px]"
                              style={{ background: item.payload?.cor }}
                              aria-hidden
                            />
                            <div className="flex flex-1 items-center justify-between gap-2 leading-none">
                              <span className="text-muted-foreground">
                                {String(name)}
                              </span>
                              <span className="font-mono font-medium text-foreground tabular-nums">
                                {oculto ? "R$ ••••" : formatBRL(Number(value))}
                              </span>
                            </div>
                          </>
                        )}
                      />
                    }
                  />
                  <Pie
                    data={fatias}
                    dataKey="valor"
                    nameKey="nome"
                    innerRadius={58}
                    outerRadius={84}
                    paddingAngle={2}
                    strokeWidth={2}
                  >
                    {fatias.map((f) => (
                      <Cell key={f.nome} fill={f.cor} />
                    ))}
                  </Pie>
                </PieChart>
              </ChartContainer>
              <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center">
                <span className="text-xs text-muted-foreground">Total</span>
                <Valor
                  centavos={total}
                  neutro
                  oculto={oculto}
                  className="text-sm font-bold"
                />
              </div>
            </div>

            <ul className="space-y-2 text-sm">
              {fatias.map((f) => (
                <li
                  key={f.nome}
                  className="grid grid-cols-[auto_1fr_auto] items-center gap-2"
                >
                  <span
                    className="size-2.5 rounded-[2px]"
                    style={{ background: f.cor }}
                    aria-hidden
                  />
                  <span className="truncate">{f.nome}</span>
                  <span className="text-right whitespace-nowrap text-muted-foreground tabular-nums">
                    {formatPct(f.pct, { casas: 1 })} ·{" "}
                    <Valor
                      centavos={f.valor}
                      neutro
                      oculto={oculto}
                      className="text-foreground"
                    />
                  </span>
                </li>
              ))}
            </ul>

            <Button asChild variant="ghost" size="sm" className="w-full">
              <Link to="/investimentos/carteira">
                Ver alocação completa
                <ArrowRight className="size-4" aria-hidden />
              </Link>
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

// --- maiores altas / baixas --------------------------------------------------------------------

function MaioresMovers({
  titulo,
  ativos,
  tipo,
  oculto,
}: {
  titulo: string
  ativos: CarteiraAtivoRV[]
  tipo: "alta" | "baixa"
  oculto: boolean
}) {
  const comPct = ativos.filter(
    (a): a is CarteiraAtivoRV & { valorizacao_pct: number } =>
      a.valorizacao_pct != null
  )
  const ordenado = comPct.sort((a, b) =>
    tipo === "alta"
      ? b.valorizacao_pct - a.valorizacao_pct
      : a.valorizacao_pct - b.valorizacao_pct
  )
  const top = ordenado
    .filter((a) =>
      tipo === "alta" ? a.valorizacao_pct >= 0 : a.valorizacao_pct < 0
    )
    .slice(0, 3)

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{titulo}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-1">
        {top.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            Sem dados no período.
          </p>
        ) : (
          top.map((a) => (
            <div
              key={a.code}
              className="grid grid-cols-[auto_1fr_auto] items-center gap-3 py-1.5"
            >
              <span
                aria-hidden
                className="grid size-9 shrink-0 place-items-center rounded-lg bg-primary/10 font-mono text-[0.6rem] font-bold text-primary"
              >
                {a.code.slice(0, 4)}
              </span>
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">{a.code}</p>
                {a.nome ? (
                  <p className="truncate text-xs text-muted-foreground">
                    {a.nome}
                  </p>
                ) : null}
              </div>
              <div className="text-right">
                <VarPct pct={a.valorizacao_pct} />
                <p className="text-xs text-muted-foreground">
                  <Valor centavos={a.valor_centavos} neutro oculto={oculto} />
                </p>
              </div>
            </div>
          ))
        )}
        <Button asChild variant="ghost" size="sm" className="mt-1 w-full">
          <Link to="/investimentos/carteira">
            Ver todas
            <ArrowRight className="size-4" aria-hidden />
          </Link>
        </Button>
      </CardContent>
    </Card>
  )
}

// --- maiores posições --------------------------------------------------------------------------

function MaioresPosicoes({
  itens,
  total,
  oculto,
}: {
  itens: CarteiraItem[]
  total: number
  oculto: boolean
}) {
  const top = [...itens]
    .sort((a, b) => b.valor_centavos - a.valor_centavos)
    .slice(0, 5)
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle className="text-base">Maiores posições</CardTitle>
        <span className="text-xs text-muted-foreground">Participação</span>
      </CardHeader>
      <CardContent className="space-y-1">
        {top.map((it) => {
          const Icone = iconeTipo(it.subtype ?? it.type)
          const part = total > 0 ? (it.valor_centavos / total) * 100 : 0
          return (
            <div
              key={it.id}
              className="grid grid-cols-[auto_1fr_auto] items-center gap-3 py-1.5"
            >
              <span
                aria-hidden
                className="grid size-9 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary"
              >
                <Icone className="size-4.5" />
              </span>
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">
                  {it.nome ?? it.code ?? "—"}
                </p>
                <Badge
                  variant="secondary"
                  className="mt-0.5 text-[0.7rem] font-normal"
                >
                  {rotuloSubtype(it.subtype) ?? rotuloTipo(it.type)}
                </Badge>
              </div>
              <div className="text-right">
                <p className="text-sm font-medium text-accent-ink tabular-nums">
                  {formatPct(part, { casas: 1 })}
                </p>
                <p className="text-xs text-muted-foreground">
                  <Valor centavos={it.valor_centavos} neutro oculto={oculto} />
                </p>
              </div>
            </div>
          )
        })}
        <Button asChild variant="ghost" size="sm" className="mt-1 w-full">
          <Link to="/investimentos/carteira">
            Ver todos os ativos
            <ArrowRight className="size-4" aria-hidden />
          </Link>
        </Button>
      </CardContent>
    </Card>
  )
}

// --- insights ----------------------------------------------------------------------------------

const INSIGHTS_KEY = "insights_invest_dispensado"

function InsightsBar({
  vg,
  numCategorias,
  contas,
  oculto,
}: {
  vg: VisaoGeralInvestimentos | undefined
  numCategorias: number
  contas: { type: string; saldo_centavos: number }[]
  oculto: boolean
}) {
  const [dispensado, setDispensado] = useState(
    () =>
      typeof localStorage !== "undefined" &&
      localStorage.getItem(INSIGHTS_KEY) === "1"
  )
  if (dispensado || !vg) return null

  const insights: string[] = []
  if (vg.vs_cdi_pp != null) {
    insights.push(
      `Sua rentabilidade acumulada está ${formatPct(Math.abs(vg.vs_cdi_pp))} ${vg.vs_cdi_pp >= 0 ? "acima" : "abaixo"} do CDI no período.`
    )
  }
  if (!oculto && vg.dividendos_mes_centavos > 0) {
    insights.push(
      `Você recebeu ${formatBRL(vg.dividendos_mes_centavos)} em dividendos neste mês.`
    )
  }
  if (numCategorias > 0) {
    insights.push(
      `Sua carteira está distribuída em ${numCategorias} tipo${numCategorias === 1 ? "" : "s"} de ativo.`
    )
  }
  const disponivel = contas
    .filter((c) => c.type !== "CREDIT" && c.saldo_centavos > 0)
    .reduce((s, c) => s + c.saldo_centavos, 0)
  if (!oculto && disponivel > 0) {
    insights.push(
      `Há ${formatBRL(disponivel)} disponíveis para um novo aporte.`
    )
  }
  if (insights.length === 0) return null

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle className="flex items-center gap-2 text-base">
          <Sparkles className="size-4 text-primary" aria-hidden />
          Insights para você
        </CardTitle>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Dispensar insights"
          onClick={() => {
            localStorage.setItem(INSIGHTS_KEY, "1")
            setDispensado(true)
          }}
        >
          <X className="size-4" />
        </Button>
      </CardHeader>
      <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {insights.map((texto, i) => (
          <div
            key={i}
            className="flex gap-2.5 rounded-lg border bg-muted/30 p-3"
          >
            <CircleCheck
              className="mt-0.5 size-4 shrink-0 text-positive"
              aria-hidden
            />
            <p className="text-sm">{texto}</p>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}
