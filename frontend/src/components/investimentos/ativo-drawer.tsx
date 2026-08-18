import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  Barcode,
  Building2,
  CalendarDays,
  ChartLine,
  Clock,
  Hash,
  Info,
  Landmark,
  Layers,
  Pencil,
  Percent,
  Plus,
  Receipt,
  Settings2,
  Sparkles,
  Tag,
  Trash2,
  TrendingUp,
  X,
} from "lucide-react"
import { useState } from "react"
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ReferenceLine,
  XAxis,
  YAxis,
} from "recharts"

import { AvatarBanco } from "@/components/contas/avatar-banco"
import { EmptyState } from "@/components/common/empty-state"
import { Valor } from "@/components/common/valor"
import { eixoBRL, linhaTooltip } from "@/components/dashboard/chart-helpers"
import { PeriodoPicker } from "@/components/dashboard/periodo-picker"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Drawer,
  DrawerClose,
  DrawerContent,
  DrawerDescription,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { useIsMobile } from "@/hooks/use-mobile"
import { useIndicadores, useIndicadoresSerie } from "@/lib/api/indicadores"
import {
  useCarteiraResumo,
  useCriarAporte,
  useEditarAporte,
  useExcluirAporte,
  useInvestimentos,
  usePosicaoCotaSerie,
  usePosicaoFundamentos,
  usePosicaoProventos,
  usePosicaoSerie,
  usePosicaoTransacoes,
  type CarteiraPosicao,
  type FundamentosFII,
  type FundamentosFIIAlocacao,
  type Investimento,
  type InvestimentoTransacao,
} from "@/lib/api/investimentos"
import {
  addDias,
  formatBRL,
  formatBucketLabel,
  formatDataISO,
  formatDate,
  hojeISO,
  subMeses,
} from "@/lib/format"
import {
  indicadorDoTitulo,
  liquidoAtual,
  projetarVencimento,
  retornoJanela,
  retornoMensal,
  serieBenchmark,
  tempoRestante,
} from "@/lib/tesouro"
import {
  agregarNegociacoes,
  type BucketCompra,
  type Negociacao,
  type TotalLado,
} from "@/lib/investimento-negociacoes"
import {
  agregarProventos,
  type BucketProvento,
  type LinhaProvento,
} from "@/lib/investimento-proventos"
import { cn } from "@/lib/utils"
import {
  fmtPct,
  fmtQtd,
  ICONE_TIPO,
  MOVIMENTO_LABEL,
  pctTexto,
  rotuloClasse,
  rotuloIndexador,
  rotuloTipo,
} from "@/lib/investimento-taxonomia"

const PRESETS_PERIODO = [
  { id: "3m", label: "3M", range: () => [subMeses(hojeISO(), 3), hojeISO()] as const },
  { id: "6m", label: "6M", range: () => [subMeses(hojeISO(), 6), hojeISO()] as const },
  { id: "12m", label: "1A", range: () => [subMeses(hojeISO(), 12), hojeISO()] as const },
  { id: "30d", label: "30d", range: () => [addDias(hojeISO(), -29), hojeISO()] as const },
]

const COR_INDICADOR: Record<string, string> = {
  cdi: "var(--chart-2)",
  selic: "var(--chart-3)",
  ipca: "var(--chart-4)",
  ibov: "var(--chart-5)",
}

const fmtDiaMes = new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "2-digit" })
const tickDia = (iso: string) => fmtDiaMes.format(new Date(`${iso}T12:00:00`))

/** Sem isto o fim do bottom sheet fica sob a barra de gestos. */
const SAFE_AREA_BOTTOM = "env(safe-area-inset-bottom)"

/** Painel do ativo (posição agrupada): resumo, performance, movimentações, dividendos e as abas
 *  ainda sem dado (indicadores/insights) marcadas como "em breve". Drawer flutuante à direita no
 *  desktop, bottom sheet no mobile. */
export function AtivoDrawer({
  posicao,
  onOpenChange,
}: {
  posicao: CarteiraPosicao | null
  onOpenChange: (aberto: boolean) => void
}) {
  // `direction` é comportamento do vaul (eixo da animação e do arraste), não dá para resolver por
  // CSS. Ao contrário da bottom nav, aqui o hook pode ser usado: o drawer nasce fechado, então o
  // `false` do primeiro paint não pisca nada.
  const isMobile = useIsMobile()
  return (
    <Drawer
      direction={isMobile ? "bottom" : "right"}
      open={posicao !== null}
      onOpenChange={onOpenChange}
    >
      {/* No lateral o painel é uma coluna travada (header fixo + abas rolando por dentro); no
          bottom sheet a rolagem é única — o header sobe junto, senão sobra pouca altura útil. */}
      <DrawerContent
        className="flex flex-col gap-0 overflow-hidden shadow-xl data-[vaul-drawer-direction=bottom]:h-[90svh] data-[vaul-drawer-direction=bottom]:max-h-[90svh] data-[vaul-drawer-direction=right]:inset-y-2 data-[vaul-drawer-direction=right]:right-2 data-[vaul-drawer-direction=right]:rounded-l-2xl data-[vaul-drawer-direction=right]:rounded-r-2xl data-[vaul-drawer-direction=right]:border data-[vaul-drawer-direction=right]:sm:max-w-xl data-[vaul-drawer-direction=right]:lg:max-w-2xl"
        style={{ paddingBottom: isMobile ? SAFE_AREA_BOTTOM : undefined }}
      >
        {posicao ? <CorpoAtivo posicao={posicao} rolagemUnica={isMobile} /> : null}
      </DrawerContent>
    </Drawer>
  )
}

/** Corpo do drawer (só monta com uma posição): cabeçalho + abas. Para FII, o cabeçalho vira a
 *  identidade do fundo (ticker + indicadores base) e o Resumo ganha performance/dados/participação.
 *  `rolagemUnica` (bottom sheet): tudo rola junto, em vez do header fixo + área de abas rolando. */
function CorpoAtivo({
  posicao: p,
  rolagemUnica,
}: {
  posicao: CarteiraPosicao
  rolagemUnica: boolean
}) {
  const ehFII = (p.subtype ?? "") === "REAL_ESTATE_FUND"
  // Todo ativo de renda fixa (Tesouro, CDB, LCI/LCA, CRI/CRA, debênture…) usa o mesmo painel do
  // Tesouro: os helpers de projeção/rentabilidade só dependem de taxa/indexador/vencimento.
  const ehRendaFixa = p.type === "FIXED_INCOME"
  const classeRF = rotuloClasse(p.type, p.subtype)
  const fund = usePosicaoFundamentos(p.investimento_ids, ehFII).data
  // Extras do título (taxa/indexador/vencimento/IR) não vêm na linha agregada — leem dos
  // investimentos da posição (compras do mesmo papel). Cacheado; só a renda fixa consome.
  const invsPosicao =
    useInvestimentos().data?.filter((i) => p.investimento_ids.includes(i.id)) ?? []
  const indexadorTexto = ehRendaFixa
    ? rotuloIndexador(invsPosicao[0]?.rate_type, invsPosicao[0]?.rate)
    : null
  return (
    // `rolagemUnica`: este wrapper é o único elemento rolável — header e abas sobem juntos. A
    // rolagem nunca pode ficar no DrawerContent: o vaul põe nele um ::after de `height: 200%`
    // abaixo do painel, que viraria 2× de vazio rolável.
    <div
      className={cn(
        "flex min-h-0 flex-1 flex-col",
        rolagemUnica ? "overflow-y-auto" : "overflow-hidden"
      )}
    >
      {/* text-left explícito também no bottom: a base centraliza o header nessa direção, o que
          desalinharia o bloco identidade + indicadores. */}
      <DrawerHeader className="shrink-0 gap-4 border-b pb-4 text-left group-data-[vaul-drawer-direction=bottom]/drawer-content:text-left">
        <div className="flex items-start gap-3">
          {ehFII ? (
            <TickerSquare code={p.code ?? p.nome ?? "?"} />
          ) : ehRendaFixa ? (
            <IconeSquare tipo={p.subtype ?? p.type} />
          ) : (
            <AvatarBanco nome={p.instituicao ?? p.nome ?? p.code ?? "?"} />
          )}
          <div className="min-w-0 flex-1">
            <DrawerTitle className="flex flex-wrap items-center gap-2 text-lg">
              {ehRendaFixa ? (p.nome ?? p.code ?? "Título") : (p.code ?? p.nome ?? "Ativo")}
              {ehFII || ehRendaFixa ? null : (
                <Badge variant="secondary">{classeRF}</Badge>
              )}
            </DrawerTitle>
            <DrawerDescription className={cn("truncate", (ehFII || ehRendaFixa) && "sr-only")}>
              {ehFII
                ? (p.nome ?? "Fundo imobiliário")
                : ehRendaFixa
                  ? indexadorTexto
                    ? `Indexador: ${indexadorTexto}`
                    : classeRF
                  : [p.nome ?? rotuloTipo(p.type), p.instituicao].filter(Boolean).join(" · ")}
            </DrawerDescription>
            {ehFII ? (
              <Badge variant="secondary" className="mt-1.5 gap-1 font-normal">
                <Building2 className="size-3" aria-hidden />
                Fundo de Investimento Imobiliário
              </Badge>
            ) : ehRendaFixa ? (
              <Badge variant="secondary" className="mt-1.5 gap-1 font-normal">
                <Landmark className="size-3" aria-hidden />
                {classeRF}
              </Badge>
            ) : null}
          </div>
          <DrawerClose asChild>
            <Button variant="ghost" size="icon" className="shrink-0" aria-label="Fechar">
              <X className="size-4" />
            </Button>
          </DrawerClose>
        </div>
        {ehFII ? (
          <IndicadoresFII posicao={p} fund={fund} />
        ) : ehRendaFixa ? (
          <IndicadoresTesouro posicao={p} liquido={liquidoAtual(invsPosicao)} />
        ) : (
          <div className="grid grid-cols-3 gap-2 text-sm">
            <Stat rotulo="Cotação">
              {p.cotacao_centavos != null ? formatBRL(p.cotacao_centavos) : "—"}
            </Stat>
            <Stat rotulo="Quantidade">
              {p.quantidade != null ? fmtQtd.format(p.quantidade) : "—"}
            </Stat>
            <Stat rotulo="Carteira">
              {p.participacao_pct != null ? `${fmtPct.format(p.participacao_pct)}%` : "—"}
            </Stat>
          </div>
        )}
      </DrawerHeader>

      <Tabs
        defaultValue="resumo"
        className={cn("flex flex-col", !rolagemUnica && "min-h-0 flex-1")}
      >
        {/* overflow-x-auto promove overflow-y a auto (quirk CSS); o sublinhado ativo (after:-5px)
            vazaria e criaria scroll vertical. pb-1.5 acomoda o sublinhado; overflow-y-hidden trava. */}
        <div className="overflow-x-auto overflow-y-hidden border-b px-4 pb-1.5">
          <TabsList variant="line" className="justify-start">
            <TabsTrigger value="resumo">Resumo</TabsTrigger>
            {!ehFII ? <TabsTrigger value="performance">Performance</TabsTrigger> : null}
            <TabsTrigger value="movimentacoes">Movimentações</TabsTrigger>
            {/* Renda fixa não paga dividendos e não tem fundamentos de mercado — sem essas abas. */}
            {!ehRendaFixa ? <TabsTrigger value="dividendos">Dividendos</TabsTrigger> : null}
            {!ehRendaFixa ? <TabsTrigger value="indicadores">Indicadores</TabsTrigger> : null}
            <TabsTrigger value="insights">Insights</TabsTrigger>
          </TabsList>
        </div>

        <div
          className={cn(
            "px-4 py-4",
            !rolagemUnica && "min-h-0 flex-1 overflow-y-auto"
          )}
        >
          <TabsContent value="resumo" className="mt-0">
            {ehRendaFixa ? (
              <ResumoTesouro posicao={p} invs={invsPosicao} />
            ) : (
              <ResumoTab posicao={p} ehFII={ehFII} fundamentos={fund} />
            )}
          </TabsContent>
          {!ehFII ? (
            <TabsContent value="performance" className="mt-0">
              {ehRendaFixa ? (
                <PerformanceTesouro
                  ids={p.investimento_ids}
                  compra={invsPosicao[0]?.purchase_date ?? undefined}
                />
              ) : (
                <PerformanceTab ids={p.investimento_ids} />
              )}
            </TabsContent>
          ) : null}
          <TabsContent value="movimentacoes" className="mt-0">
            {ehFII ? (
              <MovimentacoesFIITab ids={p.investimento_ids} />
            ) : (
              <MovimentacoesTab ids={p.investimento_ids} />
            )}
          </TabsContent>
          {!ehRendaFixa ? (
            <TabsContent value="dividendos" className="mt-0">
              {ehFII ? (
                <DividendosFIITab posicao={p} fundamentos={fund} />
              ) : (
                <DividendosTab ids={p.investimento_ids} />
              )}
            </TabsContent>
          ) : null}
          {!ehRendaFixa ? (
            <TabsContent value="indicadores" className="mt-0">
              {ehFII ? (
                <IndicadoresFIITab ids={p.investimento_ids} />
              ) : (
                <EmBreve
                  titulo="Indicadores em breve"
                  descricao="P/L, P/VP, dividend yield de mercado, liquidez e setor dependem de uma fonte de fundamentos ainda não conectada para esta classe."
                />
              )}
            </TabsContent>
          ) : null}
          <TabsContent value="insights" className="mt-0">
            <InsightsTab />
          </TabsContent>
        </div>
      </Tabs>
    </div>
  )
}

function Stat({
  rotulo,
  children,
  destaque,
}: {
  rotulo: string
  children: React.ReactNode
  destaque?: boolean
}) {
  return (
    <div className="rounded-lg border bg-background/60 px-2.5 py-1.5">
      <p className="text-xs text-muted-foreground">{rotulo}</p>
      <p className={cn("truncate font-medium tabular-nums", destaque && "text-accent-ink")}>
        {children}
      </p>
    </div>
  )
}

/** Quadrado com o ticker do FII (imagem 1). Substitui o avatar de banco só para FIIs. */
function TickerSquare({ code }: { code: string }) {
  return (
    <div className="grid size-14 shrink-0 place-items-center rounded-xl bg-primary/10 px-1">
      <span className="font-mono text-xs leading-none font-semibold tracking-tight text-accent-ink text-balance break-all">
        {code}
      </span>
    </div>
  )
}

/** Quadrado com o ícone do tipo (Tesouro Direto → Landmark), no mesmo estilo do TickerSquare. */
function IconeSquare({ tipo }: { tipo: string }) {
  const Icone = ICONE_TIPO[tipo] ?? Landmark
  return (
    <div className="grid size-14 shrink-0 place-items-center rounded-xl bg-primary/10">
      <Icone className="size-6 text-accent-ink" aria-hidden />
    </div>
  )
}

/** Indicador base do cabeçalho do FII (imagem 2): rótulo miúdo + valor forte, sem moldura. */
function Indicador({
  rotulo,
  children,
  sub,
  destaque,
}: {
  rotulo: string
  children: React.ReactNode
  sub?: string
  destaque?: boolean
}) {
  return (
    <div className="min-w-0">
      <p className="truncate text-xs text-muted-foreground">{rotulo}</p>
      <div className={cn("text-base font-semibold tabular-nums", destaque && "text-accent-ink")}>
        {children}
      </div>
      {sub ? <p className="truncate text-[0.7rem] text-muted-foreground">{sub}</p> : null}
    </div>
  )
}

/** Linha de indicadores base do FII: preço (+var. diária), quantidade, investido, preço médio,
 *  DY 12M e resultado. A variação diária vem dos 2 últimos fechamentos da série da cota (brapi). */
function IndicadoresFII({
  posicao: p,
  fund,
}: {
  posicao: CarteiraPosicao
  fund: FundamentosFII | undefined
}) {
  // ponytail: variação "desde o último fechamento" (2 últimos pontos), não estritamente vs. ontem
  // de calendário em feriados; some junto com a série quando não há token brapi.
  const serie =
    usePosicaoCotaSerie(
      p.investimento_ids,
      { inicio: addDias(hojeISO(), -12), fim: hojeISO() },
      true
    ).data ?? []
  const ultimo = serie.at(-1)
  const penultimo = serie.at(-2)
  const variacaoPct =
    ultimo && penultimo && penultimo.valor_centavos > 0
      ? (ultimo.valor_centavos / penultimo.valor_centavos - 1) * 100
      : null
  const dataCota = ultimo?.data ?? fund?.data_referencia ?? null
  return (
    <div className="my-2 grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-3">
      <Indicador
        rotulo="Preço atual"
        sub={dataCota ? `Cota em ${formatDataISO(dataCota)}` : undefined}
      >
        <span className="flex flex-wrap items-baseline gap-x-1.5">
          {p.cotacao_centavos != null ? formatBRL(p.cotacao_centavos) : "—"}
          {variacaoPct != null ? (
            <span
              className={cn(
                "inline-flex items-center gap-0.5 text-xs font-medium",
                variacaoPct >= 0 ? "text-positive" : "text-negative"
              )}
            >
              {variacaoPct >= 0 ? (
                <ArrowUp className="size-3" aria-hidden />
              ) : (
                <ArrowDown className="size-3" aria-hidden />
              )}
              {pctTexto(variacaoPct)}
            </span>
          ) : null}
        </span>
      </Indicador>
      <Indicador rotulo="Quantidade">
        {p.quantidade != null ? fmtQtd.format(p.quantidade) : "—"}
      </Indicador>
      <Indicador rotulo="Valor investido">
        {p.investido_centavos != null ? formatBRL(p.investido_centavos) : "—"}
      </Indicador>
      <Indicador rotulo="Valor médio da cota">
        {p.preco_medio_centavos != null ? formatBRL(p.preco_medio_centavos) : "—"}
      </Indicador>
      <Indicador rotulo="Dividend Yield (12M)" destaque>
        {fund?.dividend_yield_12m_pct != null
          ? `${fmtPct.format(fund.dividend_yield_12m_pct)}%`
          : "—"}
      </Indicador>
      <Indicador rotulo="Meu resultado">
        {p.resultado_centavos != null ? (
          <span className="flex flex-wrap items-baseline gap-x-1.5">
            <Valor centavos={p.resultado_centavos} sinal />
            {p.resultado_pct != null ? (
              <span className="text-xs text-muted-foreground">{pctTexto(p.resultado_pct)}</span>
            ) : null}
          </span>
        ) : (
          "—"
        )}
      </Indicador>
    </div>
  )
}

/** Cabeçalho da renda fixa (Tesouro, CDB, LCI/LCA, CRI/CRA, debênture): 7 indicadores — preço
 *  unitário, quantidade, investido, valor atual, lucro, rentabilidade e valor líquido (líq. de IR). */
function IndicadoresTesouro({
  posicao: p,
  liquido,
}: {
  posicao: CarteiraPosicao
  liquido: number | null
}) {
  return (
    <div className="my-2 grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-3">
      <Indicador rotulo="Preço unitário">
        {p.cotacao_centavos != null ? formatBRL(p.cotacao_centavos) : "—"}
      </Indicador>
      <Indicador rotulo="Quantidade">
        {p.quantidade != null ? fmtQtd.format(p.quantidade) : "—"}
      </Indicador>
      <Indicador rotulo="Valor investido">
        {p.investido_centavos != null ? formatBRL(p.investido_centavos) : "—"}
      </Indicador>
      <Indicador rotulo="Valor atual">{formatBRL(p.valor_centavos)}</Indicador>
      <Indicador rotulo="Lucro">
        {p.resultado_centavos != null ? <Valor centavos={p.resultado_centavos} sinal /> : "—"}
      </Indicador>
      <Indicador rotulo="Rentabilidade">
        {p.resultado_pct != null ? (
          <span className={cn(p.resultado_pct >= 0 ? "text-positive" : "text-negative")}>
            {pctTexto(p.resultado_pct)}
          </span>
        ) : (
          "—"
        )}
      </Indicador>
      <Indicador rotulo="Valor líquido">{liquido != null ? formatBRL(liquido) : "—"}</Indicador>
    </div>
  )
}

function Linha({ rotulo, children }: { rotulo: string; children: React.ReactNode }) {
  if (children == null) return null
  return (
    <div className="flex items-start justify-between gap-4 py-2">
      <dt className="shrink-0 text-muted-foreground">{rotulo}</dt>
      <dd className="min-w-0 text-right font-medium tabular-nums break-words">{children}</dd>
    </div>
  )
}

/** Resumo dos ativos sem painel próprio (renda variável, ETFs, fundos): números da posição e, para
 *  FII, "Sobre o fundo" (CVM) e a evolução do valor da cota. Renda fixa usa `ResumoTesouro`. */
function ResumoTab({
  posicao: p,
  ehFII,
  fundamentos,
}: {
  posicao: CarteiraPosicao
  ehFII: boolean
  fundamentos: FundamentosFII | undefined
}) {
  return (
    <>
      {p.historico_incompleto ? (
        <div className="mb-3 flex items-start gap-2 rounded-lg border border-amber-500/40 bg-amber-50 p-3 dark:bg-amber-950/30">
          <AlertTriangle
            className="mt-0.5 size-4 shrink-0 text-amber-600 dark:text-amber-500"
            aria-hidden
          />
          <p className="text-xs text-foreground">
            Preço médio e valor investido estão calculados só com as compras que o banco informou
            (últimos 12 meses). Adicione seus aportes anteriores na aba{" "}
            <span className="font-medium">Movimentações</span> para o cálculo ficar completo.
          </p>
        </div>
      ) : null}
      {ehFII ? (
        <div className="space-y-6">
          <PerformanceFII ids={p.investimento_ids} />
          {fundamentos?.disponivel ? <DadosFII f={fundamentos} ticker={p.code} /> : null}
          <ParticipacaoFII posicao={p} />
        </div>
      ) : (
        <dl className="text-sm">
          <Linha rotulo="Valor investido">
            {p.investido_centavos != null ? <Valor centavos={p.investido_centavos} neutro /> : "—"}
          </Linha>
          <Linha rotulo="Valor atual">
            <Valor centavos={p.valor_centavos} neutro />
          </Linha>
          <Linha rotulo="Resultado">
            {p.resultado_centavos != null ? (
              <span className="inline-flex items-center gap-2">
                <Valor centavos={p.resultado_centavos} sinal />
                {p.resultado_pct != null ? (
                  <span className="text-xs text-muted-foreground">
                    {pctTexto(p.resultado_pct)}
                  </span>
                ) : null}
              </span>
            ) : (
              "—"
            )}
          </Linha>
          <Linha rotulo="Preço médio">
            {p.preco_medio_centavos != null ? formatBRL(p.preco_medio_centavos) : "—"}
          </Linha>
          <Linha rotulo="Cotação">
            {p.cotacao_centavos != null ? formatBRL(p.cotacao_centavos) : "—"}
          </Linha>
          <Linha rotulo="Quantidade">
            {p.quantidade != null ? fmtQtd.format(p.quantidade) : "—"}
          </Linha>
          <Linha rotulo="Participação na carteira">
            {p.participacao_pct != null ? `${fmtPct.format(p.participacao_pct)}%` : "—"}
          </Linha>
          {p.instituicao ? <Linha rotulo="Instituição">{p.instituicao}</Linha> : null}
        </dl>
      )}
    </>
  )
}

const TIPO_FUNDO: Record<string, string> = {
  tijolo: "FII de Tijolo",
  papel: "FII de Papel",
  hibrido: "Híbrido",
  fof: "Fundo de Fundos",
}

/** Ícone por linha de "Dados do fundo" (member-access p/ não reprovar no lint static-components). */
const DADOS_ICONE = {
  segmento: Layers,
  tipo: Building2,
  gestao: Settings2,
  administrador: Landmark,
  inicio: CalendarDays,
  cnpj: Hash,
  ticker: Tag,
  isin: Barcode,
  tributacao: Receipt,
} as const

/** "Dados do fundo" (imagem 4) — cadastro do FII (CVM) em lista com ícone. Só linhas com valor. */
function DadosFII({ f, ticker }: { f: FundamentosFII; ticker: string | null }) {
  const linhas = (
    [
      { chave: "segmento", rotulo: "Segmento", valor: f.segmento ?? null },
      { chave: "tipo", rotulo: "Tipo", valor: f.tipo ? (TIPO_FUNDO[f.tipo] ?? f.tipo) : null },
      { chave: "gestao", rotulo: "Gestão", valor: f.tipo_gestao ?? null },
      { chave: "administrador", rotulo: "Administrador", valor: f.administrador_nome ?? null },
      {
        chave: "inicio",
        rotulo: "Início do fundo",
        valor: f.data_funcionamento ? formatDataISO(f.data_funcionamento) : null,
      },
      { chave: "cnpj", rotulo: "CNPJ", valor: f.cnpj ?? null },
      { chave: "ticker", rotulo: "Ticker", valor: ticker },
      { chave: "isin", rotulo: "ISIN", valor: f.isin ?? null },
      { chave: "tributacao", rotulo: "Tributação", valor: "Isento de IR (rendimentos)" },
    ] satisfies { chave: keyof typeof DADOS_ICONE; rotulo: string; valor: string | null }[]
  ).filter((l) => l.valor)
  return (
    <section>
      <h3 className="mb-1 text-sm font-medium">Dados do fundo</h3>
      <dl className="divide-y divide-border/60 text-sm">
        {linhas.map((l) => {
          const Icone = DADOS_ICONE[l.chave]
          return (
            <div key={l.chave} className="flex items-center justify-between gap-4 py-2.5">
              <dt className="flex items-center gap-2 text-muted-foreground">
                <Icone className="size-4 shrink-0 text-muted-foreground/70" aria-hidden />
                {l.rotulo}
              </dt>
              <dd className="min-w-0 truncate text-right font-medium tabular-nums">{l.valor}</dd>
            </div>
          )
        })}
      </dl>
    </section>
  )
}

// O plano grátis da brapi só serve os ranges 1d/5d/1mo/3mo com interval=1d (intraday e 6M+ dão
// HTTP 400). Presets ≤ 88 dias → `_range_brapi` os mapeia p/ 1mo/3mo (permitidos). Horizonte maior
// exige plano pago. `1d` ficou de fora: renderiza 1 ponto só (sem linha).
const PRESETS_FII = [
  { id: "5d", label: "5D", range: () => [addDias(hojeISO(), -5), hojeISO()] as const },
  { id: "1m", label: "1M", range: () => [addDias(hojeISO(), -30), hojeISO()] as const },
  { id: "3m", label: "3M", range: () => [addDias(hojeISO(), -88), hojeISO()] as const },
]

/** Performance do próprio FII (preço da cota normalizado em %) vs. CDI e IBOV no período.
 *  Distinto da aba Performance, que é a rentabilidade (TWR) das MINHAS cotas. */
function PerformanceFII({ ids }: { ids: number[] }) {
  const [[inicio, fim], setPeriodo] = useState<readonly [string, string]>(PRESETS_FII[2].range())
  const serie = usePosicaoCotaSerie(ids, { inicio, fim }, true)
  const pontos = serie.data ?? []
  const base = pontos[0]?.valor_centavos ?? 0
  const inicioComum = pontos[0]?.data ?? inicio
  const indicadores = useIndicadores()
  const disponiveis = new Set((indicadores.data ?? []).map((i) => i.codigo))
  // IBOV só existe com token brapi (useIndicadores já filtra); CDI é BCB, sempre presente.
  const bench = ["cdi", "ibov"].filter((c) => disponiveis.has(c))
  const benchSerie = useIndicadoresSerie(pontos.length >= 2 ? bench : [], {
    inicio: inicioComum,
    fim,
  })

  const config: ChartConfig = { fii: { label: "Este FII", color: "var(--primary)" } }
  for (const i of indicadores.data ?? [])
    if (bench.includes(i.codigo))
      config[i.codigo] = { label: i.nome, color: COR_INDICADOR[i.codigo] ?? "var(--chart-5)" }

  const porData = new Map<string, Record<string, number | string>>()
  for (const pt of pontos)
    porData.set(pt.data, {
      data: pt.data,
      fii: base > 0 ? (pt.valor_centavos / base - 1) * 100 : 0,
    })
  for (const s of benchSerie.data ?? [])
    for (const pt of s.pontos) {
      const linha = porData.get(pt.data)
      if (linha) linha[s.codigo] = pt.acumulado_pct
    }
  const dados = [...porData.values()].sort((a, b) => String(a.data).localeCompare(String(b.data)))
  const ultimo = dados.at(-1)

  const presetAtivo =
    PRESETS_FII.find((pp) => {
      const [i, f] = pp.range()
      return i === inicio && f === fim
    })?.id ?? ""

  const legenda = ["fii", ...bench].map((codigo) => ({
    codigo,
    label: config[codigo]?.label ?? codigo,
    color: config[codigo]?.color,
  }))

  return (
    <section>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-medium">Performance</h3>
        <ToggleGroup
          type="single"
          size="sm"
          variant="outline"
          spacing={0}
          value={presetAtivo}
          onValueChange={(v) => {
            const pp = PRESETS_FII.find((x) => x.id === v)
            if (pp) setPeriodo(pp.range())
          }}
          aria-label="Período"
        >
          {PRESETS_FII.map((pp) => (
            <ToggleGroupItem key={pp.id} value={pp.id}>
              {pp.label}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      </div>
      {serie.isLoading ? (
        <Skeleton className="h-[200px] w-full" />
      ) : pontos.length < 2 ? (
        <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed px-6 py-10 text-center">
          <ChartLine className="size-6 text-muted-foreground" aria-hidden />
          <p className="text-sm font-medium">Sem histórico de preço</p>
          <p className="max-w-xs text-xs text-balance text-muted-foreground">
            A evolução da cota vem do mercado (brapi) e precisa do token configurado em Conexões.
          </p>
        </div>
      ) : (
        <>
          <ChartContainer config={config} className="aspect-auto h-[200px] w-full">
            <LineChart data={dados}>
              <CartesianGrid vertical={false} strokeDasharray="3 3" />
              <XAxis
                dataKey="data"
                tickLine={false}
                axisLine={false}
                tickMargin={8}
                minTickGap={32}
                tickFormatter={tickDia}
              />
              <YAxis
                tickLine={false}
                axisLine={false}
                width={48}
                tickFormatter={(v: number) => pctTexto(v)}
              />
              <ChartTooltip
                content={
                  <ChartTooltipContent
                    labelFormatter={(_, payload) =>
                      formatDate(String(payload?.[0]?.payload?.data ?? ""))
                    }
                    formatter={(value, name, item) => (
                      <>
                        <span
                          className="mt-0.5 size-2.5 shrink-0 rounded-[2px]"
                          style={{ background: item.color }}
                          aria-hidden
                        />
                        <div className="flex flex-1 items-center justify-between gap-2 leading-none">
                          <span className="text-muted-foreground">
                            {config[String(name)]?.label ?? name}
                          </span>
                          <span className="font-mono font-medium tabular-nums text-foreground">
                            {pctTexto(Number(value))}
                          </span>
                        </div>
                      </>
                    )}
                  />
                }
              />
              <Line
                dataKey="fii"
                stroke="var(--color-fii)"
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
              {bench.map((codigo) => (
                <Line
                  key={codigo}
                  dataKey={codigo}
                  stroke={`var(--color-${codigo})`}
                  strokeWidth={1.5}
                  strokeDasharray={codigo === "cdi" ? "4 4" : undefined}
                  dot={false}
                  isAnimationActive={false}
                />
              ))}
            </LineChart>
          </ChartContainer>
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
            {legenda.map((l) => {
              const val = ultimo?.[l.codigo]
              return (
                <span key={l.codigo} className="inline-flex items-center gap-1.5 text-xs">
                  <span
                    className="size-2 rounded-full"
                    style={{ background: l.color }}
                    aria-hidden
                  />
                  <span className="text-muted-foreground">{l.label}</span>
                  {typeof val === "number" ? (
                    <span className="font-medium tabular-nums text-foreground">
                      {pctTexto(val)}
                    </span>
                  ) : null}
                </span>
              )
            })}
          </div>
          <RentabilidadeFII ids={ids} inicioSelecionado={inicio} />
        </>
      )}
    </section>
  )
}

/** Rentabilidade do preço do FII em janelas fixas (imagem: "No período", "3 meses"…). O plano grátis
 *  da brapi só serve histórico ≤ 3 meses, então 6M/12M/desde o IPO ficam de fora (exigem plano pago).
 *  Tudo derivado de uma única série de 3 meses (o teto do plano). */
function RentabilidadeFII({
  ids,
  inicioSelecionado,
}: {
  ids: number[]
  inicioSelecionado: string
}) {
  const serie = usePosicaoCotaSerie(ids, { inicio: addDias(hojeISO(), -88), fim: hojeISO() }, true)
    .data ?? []
  if (serie.length < 2) return null
  const ultimo = serie[serie.length - 1].valor_centavos
  // Retorno do preço desde o 1º ponto cuja data ≥ iso (datas ISO comparam como string).
  const retornoDesde = (iso: string): number | null => {
    const base = serie.find((p) => p.data >= iso)?.valor_centavos
    return base != null && base > 0 ? (ultimo / base - 1) * 100 : null
  }
  // Mesmas fronteiras dos presets do gráfico → "No período" bate com a janela fixa quando coincidem.
  const itens = [
    { rotulo: "No período", pct: retornoDesde(inicioSelecionado) },
    { rotulo: "1 mês", pct: retornoDesde(addDias(hojeISO(), -30)) },
    { rotulo: "3 meses", pct: retornoDesde(addDias(hojeISO(), -88)) },
  ]
  return (
    <div className="mt-3 grid grid-cols-3 gap-x-4 gap-y-2 border-t pt-3">
      {itens.map((it) => (
        <RetornoItem key={it.rotulo} rotulo={it.rotulo} pct={it.pct} />
      ))}
    </div>
  )
}

/** Um retorno de janela: rótulo miúdo + % com seta e cor por sinal (verde/vermelho). */
function RetornoItem({ rotulo, pct }: { rotulo: string; pct: number | null }) {
  return (
    <div className="min-w-0">
      <p className="truncate text-xs text-muted-foreground">{rotulo}</p>
      {pct == null ? (
        <p className="text-sm font-semibold text-muted-foreground">—</p>
      ) : (
        <p
          className={cn(
            "inline-flex items-center gap-1 text-sm font-semibold tabular-nums",
            pct >= 0 ? "text-positive" : "text-negative"
          )}
        >
          {pct >= 0 ? (
            <ArrowUp className="size-3.5" aria-hidden />
          ) : (
            <ArrowDown className="size-3.5" aria-hidden />
          )}
          {pctTexto(pct)}
        </p>
      )}
    </div>
  )
}

/** Participação do FII em três recortes (imagem: mini-donuts): carteira, renda variável e FIIs. */
function ParticipacaoFII({ posicao: p }: { posicao: CarteiraPosicao }) {
  const resumo = useCarteiraResumo().data
  if (!resumo) return <Skeleton className="h-[132px] w-full" />
  const rv = resumo.grupos
    .filter((g) => g.type === "EQUITY" || g.type === "ETF")
    .reduce((s, g) => s + g.valor_centavos, 0)
  const fiiTotal =
    resumo.alocacao.find((a) => a.tipo === "REAL_ESTATE_FUND")?.valor_centavos ?? 0
  const pctCarteira =
    p.participacao_pct ??
    (resumo.totais.valor_centavos > 0
      ? (p.valor_centavos / resumo.totais.valor_centavos) * 100
      : null)
  const itens = [
    { rotulo: "Da carteira", pct: pctCarteira },
    { rotulo: "Da renda variável", pct: rv > 0 ? (p.valor_centavos / rv) * 100 : null },
    { rotulo: "Dos FIIs", pct: fiiTotal > 0 ? (p.valor_centavos / fiiTotal) * 100 : null },
  ]
  return (
    <section>
      <h3 className="mb-3 text-sm font-medium">Participação</h3>
      <div className="grid grid-cols-3 gap-2">
        {itens.map((it) => (
          <DonutParticipacao key={it.rotulo} rotulo={it.rotulo} pct={it.pct} />
        ))}
      </div>
    </section>
  )
}

/** Um anel de participação: fatia em accent, resto neutro, % no centro. */
function DonutParticipacao({ rotulo, pct }: { rotulo: string; pct: number | null }) {
  const valor = pct == null ? 0 : Math.max(0, Math.min(100, pct))
  const dados = [
    { nome: "fatia", v: valor },
    { nome: "resto", v: 100 - valor },
  ]
  return (
    <div className="flex flex-col items-center gap-1.5">
      <div className="relative">
        <ChartContainer config={{}} className="aspect-square h-[92px]">
          <PieChart>
            <Pie
              data={dados}
              dataKey="v"
              nameKey="nome"
              innerRadius={30}
              outerRadius={42}
              startAngle={90}
              endAngle={-270}
              strokeWidth={0}
              isAnimationActive={false}
            >
              <Cell fill="var(--primary)" />
              <Cell fill="var(--muted)" />
            </Pie>
          </PieChart>
        </ChartContainer>
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <span className="text-sm font-semibold tabular-nums text-accent-ink">
            {pct == null ? "—" : `${fmtPct.format(pct)}%`}
          </span>
        </div>
      </div>
      <span className="text-center text-xs text-muted-foreground">{rotulo}</span>
    </div>
  )
}

/** Performance: rentabilidade acumulada (TWR) da posição vs. indicadores. "Evolução do preço"
 *  unitária fica para uma fase futura (precisa da série de cotação por ticker). */
function PerformanceTab({ ids }: { ids: number[] }) {
  const [[inicio, fim], setPeriodo] = useState<readonly [string, string]>(
    PRESETS_PERIODO[2].range()
  )
  const [selecionados, setSelecionados] = useState<string[]>(["cdi"])
  const indicadores = useIndicadores()
  const serie = usePosicaoSerie(ids, { inicio, fim })
  const pontos = serie.data?.pontos ?? []
  const inicioComum = pontos[0]?.data ?? inicio
  const indicadoresSerie = useIndicadoresSerie(
    pontos.length >= 2 ? selecionados : [],
    { inicio: inicioComum, fim }
  )

  const config: ChartConfig = { ativo: { label: "Este ativo", color: "var(--primary)" } }
  for (const i of indicadores.data ?? []) {
    config[i.codigo] = { label: i.nome, color: COR_INDICADOR[i.codigo] ?? "var(--chart-5)" }
  }

  const porData = new Map<string, Record<string, number | string>>()
  for (const pt of pontos) porData.set(pt.data, { data: pt.data, ativo: pt.acumulado_pct })
  for (const s of indicadoresSerie.data ?? [])
    for (const pt of s.pontos) {
      const linha = porData.get(pt.data)
      if (linha) linha[s.codigo] = pt.acumulado_pct
    }
  const dadosChart = [...porData.values()].sort((a, b) =>
    String(a.data).localeCompare(String(b.data))
  )

  const presetAtivo =
    PRESETS_PERIODO.find((pp) => {
      const [i, f] = pp.range()
      return i === inicio && f === fim
    })?.id ?? ""

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <ToggleGroup
          type="single"
          size="sm"
          variant="outline"
          spacing={0}
          value={presetAtivo}
          onValueChange={(v) => {
            const pp = PRESETS_PERIODO.find((x) => x.id === v)
            if (pp) setPeriodo(pp.range())
          }}
          aria-label="Período"
        >
          {PRESETS_PERIODO.map((pp) => (
            <ToggleGroupItem key={pp.id} value={pp.id}>
              {pp.label}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
        <PeriodoPicker inicio={inicio} fim={fim} onChange={(i, f) => setPeriodo([i, f])} />
      </div>

      {indicadores.data && indicadores.data.length > 0 ? (
        <ToggleGroup
          type="multiple"
          size="sm"
          variant="outline"
          spacing={0}
          value={selecionados}
          onValueChange={setSelecionados}
          aria-label="Comparar com"
        >
          {indicadores.data.map((i) => (
            <ToggleGroupItem key={i.codigo} value={i.codigo}>
              {i.nome}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      ) : null}

      {serie.isLoading ? (
        <Skeleton className="h-[240px] w-full" />
      ) : pontos.length < 2 ? (
        <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed px-6 py-10 text-center">
          <ChartLine className="size-6 text-muted-foreground" aria-hidden />
          <p className="text-sm font-medium">O histórico acumula a partir de agora</p>
          <p className="max-w-xs text-xs text-balance text-muted-foreground">
            Cada sincronização grava um ponto diário; a curva aparece conforme os dias passam.
            Ativos de bolsa com ticker ganham o passado pelo preço de mercado.
          </p>
        </div>
      ) : (
        <ChartContainer config={config} className="aspect-auto h-[240px] w-full">
          <LineChart data={dadosChart}>
            <CartesianGrid vertical={false} strokeDasharray="3 3" />
            <XAxis
              dataKey="data"
              tickLine={false}
              axisLine={false}
              tickMargin={8}
              minTickGap={32}
              tickFormatter={tickDia}
            />
            <YAxis
              tickLine={false}
              axisLine={false}
              width={48}
              tickFormatter={(v: number) => pctTexto(v)}
            />
            <ChartTooltip
              content={
                <ChartTooltipContent
                  labelFormatter={(_, payload) =>
                    formatDate(String(payload?.[0]?.payload?.data ?? ""))
                  }
                  formatter={(value, name, item) => (
                    <>
                      <span
                        className="mt-0.5 size-2.5 shrink-0 rounded-[2px]"
                        style={{ background: item.color }}
                        aria-hidden
                      />
                      <div className="flex flex-1 items-center justify-between gap-2 leading-none">
                        <span className="text-muted-foreground">
                          {config[String(name)]?.label ?? name}
                        </span>
                        <span className="font-mono font-medium tabular-nums text-foreground">
                          {pctTexto(Number(value))}
                        </span>
                      </div>
                    </>
                  )}
                />
              }
            />
            <ChartLegend content={<ChartLegendContent />} />
            <Line
              dataKey="ativo"
              stroke="var(--color-ativo)"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
            {selecionados.map((codigo) => (
              <Line
                key={codigo}
                dataKey={codigo}
                stroke={`var(--color-${codigo})`}
                strokeWidth={1.5}
                strokeDasharray="4 3"
                dot={false}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ChartContainer>
      )}
      <p className="text-xs text-muted-foreground">
        Evolução do preço unitário e da posição em reais chegam em breve.
      </p>
    </div>
  )
}

// --- Renda fixa (Tesouro, CDB, LCI/LCA, CRI/CRA, debênture) --------------------------------------

/** Resumo da renda fixa: rentabilidade, dados do título, projeção de vencimento e a evolução do
 *  investimento em R$. Espelha o padrão visual do Resumo de FII. */
function ResumoTesouro({ posicao: p, invs }: { posicao: CarteiraPosicao; invs: Investimento[] }) {
  const rf = invs[0]
  return (
    <div className="space-y-6">
      <RentabilidadeTesouro posicao={p} rf={rf} />
      <InfoTitulo rf={rf} />
      <EsperadoVencimento posicao={p} rf={rf} />
      <EvolucaoInvestimento ids={p.investimento_ids} compra={rf?.purchase_date ?? undefined} />
    </div>
  )
}

/** Rentabilidade em três janelas (imagem): desde a compra, no ano e últimos 12 meses. "Desde a
 *  compra" vem da posição (resultado); as outras da série TWR (12m usa a taxa do Pluggy se houver). */
function RentabilidadeTesouro({
  posicao: p,
  rf,
}: {
  posicao: CarteiraPosicao
  rf: Investimento | undefined
}) {
  const serie = usePosicaoSerie(p.investimento_ids, {
    inicio: subMeses(hojeISO(), 12),
    fim: hojeISO(),
  })
  const pontos = serie.data?.pontos ?? []
  const anoISO = `${hojeISO().slice(0, 4)}-01-01`
  const noAno = retornoJanela(pontos, anoISO)
  const doze = retornoJanela(pontos, pontos[0]?.data ?? anoISO)
  const pct12 =
    rf?.last_twelve_months_rate != null ? Number(rf.last_twelve_months_rate) : (doze?.pct ?? null)
  const itens = [
    { rotulo: "Desde a compra", pct: p.resultado_pct ?? null, ganho: p.resultado_centavos ?? null },
    { rotulo: "No ano", pct: noAno?.pct ?? null, ganho: noAno?.ganho_centavos ?? null },
    { rotulo: "Últimos 12 meses", pct: pct12, ganho: doze?.ganho_centavos ?? null },
  ]
  return (
    <section>
      <h3 className="mb-3 text-sm font-medium">Rentabilidade</h3>
      <div className="grid grid-cols-3 gap-2">
        {itens.map((it) => (
          <RetornoTesouro key={it.rotulo} rotulo={it.rotulo} pct={it.pct} ganho={it.ganho} />
        ))}
      </div>
    </section>
  )
}

/** Um card de rentabilidade (janela): rótulo + % grande com cor por sinal + o ganho em R$ abaixo. */
function RetornoTesouro({
  rotulo,
  pct,
  ganho,
}: {
  rotulo: string
  pct: number | null
  ganho: number | null
}) {
  return (
    <div className="rounded-lg border bg-background/60 p-3">
      <p className="truncate text-xs text-muted-foreground">{rotulo}</p>
      {pct == null ? (
        <p className="mt-1 text-lg font-semibold text-muted-foreground">—</p>
      ) : (
        <p
          className={cn(
            "mt-1 text-lg font-semibold tabular-nums",
            pct >= 0 ? "text-positive" : "text-negative"
          )}
        >
          {pctTexto(pct)}
        </p>
      )}
      <div className="text-xs">{ganho != null ? <Valor centavos={ganho} sinal /> : null}</div>
    </div>
  )
}

/** Ícone por linha de "Informações do título" (member-access p/ o lint static-components). */
const INFO_TITULO_ICONE = {
  vencimento: CalendarDays,
  indexador: Percent,
  taxa: TrendingUp,
  compra: Tag,
  liquidacao: Clock,
  custodia: Landmark,
} as const

/** Informações do título (imagem): vencimento (+ tempo restante), indexador, taxa, data de compra,
 *  liquidação e custódia. ponytail: liquidação "D+1" e custódia "B3" são constantes do Tesouro
 *  Direto — o Pluggy não as fornece para investimentos. */
function InfoTitulo({ rf }: { rf: Investimento | undefined }) {
  const indexador = rotuloIndexador(rf?.rate_type, rf?.rate)
  const restante = rf?.due_date ? tempoRestante(rf.due_date) : null
  // Liquidação D+1 e custódia B3 só valem para o Tesouro Direto; nos demais títulos (CDB, LCI…) a
  // liquidez varia, então essas linhas ficam de fora.
  const ehTesouro = (rf?.subtype ?? "") === "TREASURY"
  const linhas = (
    [
      {
        chave: "vencimento",
        rotulo: "Vencimento",
        valor: rf?.due_date ? formatDate(rf.due_date) : null,
        sub: restante ? `${restante} restantes` : null,
      },
      { chave: "indexador", rotulo: "Indexador", valor: indexador, sub: null },
      {
        chave: "taxa",
        rotulo: "Taxa contratada",
        valor: rf?.rate != null ? `${fmtPct.format(Number(rf.rate))}% a.a.` : null,
        sub: null,
      },
      {
        chave: "compra",
        rotulo: "Data de compra",
        valor: rf?.purchase_date ? formatDate(rf.purchase_date) : null,
        sub: null,
      },
      { chave: "liquidacao", rotulo: "Liquidação", valor: ehTesouro ? "D+1" : null, sub: null },
      { chave: "custodia", rotulo: "Custódia", valor: ehTesouro ? "B3" : null, sub: null },
    ] satisfies {
      chave: keyof typeof INFO_TITULO_ICONE
      rotulo: string
      valor: string | null
      sub: string | null
    }[]
  ).filter((l) => l.valor)
  return (
    <section>
      <h3 className="mb-1 text-sm font-medium">Informações do título</h3>
      <dl className="divide-y divide-border/60 text-sm">
        {linhas.map((l) => {
          const Icone = INFO_TITULO_ICONE[l.chave]
          return (
            <div key={l.chave} className="flex items-center justify-between gap-4 py-2.5">
              <dt className="flex items-center gap-2 text-muted-foreground">
                <Icone className="size-4 shrink-0 text-muted-foreground/70" aria-hidden />
                {l.rotulo}
              </dt>
              <dd className="min-w-0 text-right font-medium tabular-nums">
                {l.valor}
                {l.sub ? (
                  <span className="block text-xs font-normal text-muted-foreground">{l.sub}</span>
                ) : null}
              </dd>
            </div>
          )
        })}
      </dl>
    </section>
  )
}

/** Valor esperado no vencimento (estimativa): capitaliza o valor bruto atual por juros compostos à
 *  taxa efetiva até o vencimento. Pós-fixados/indexados usam o **nível atual** do indexador (SELIC/
 *  IPCA/CDI dos últimos 12 meses, via BCB) + o spread contratado; prefixado usa a taxa travada. */
function EsperadoVencimento({
  posicao: p,
  rf,
}: {
  posicao: CarteiraPosicao
  rf: Investimento | undefined
}) {
  // Nível atual do indexador = retorno acumulado dos últimos 12 meses (≈ taxa anual corrente).
  const codigo = indicadorDoTitulo(rf?.rate_type)
  const nivelSerie = useIndicadoresSerie(codigo ? [codigo] : [], {
    inicio: subMeses(hojeISO(), 12),
    fim: hojeISO(),
  })
  const pontosNivel = nivelSerie.data?.[0]?.pontos ?? []
  const nivelAnual = pontosNivel.length ? pontosNivel[pontosNivel.length - 1]!.acumulado_pct / 100 : null

  if (!rf?.due_date) return null
  const proj = projetarVencimento(
    p.valor_centavos,
    p.investido_centavos ?? p.valor_centavos,
    rf.due_date,
    { rateType: rf.rate_type, rate: rf.rate, annualRate: rf.annual_rate, taxExempt: rf.tax_exempt },
    nivelAnual
  )
  if (!proj) return null
  const lucro = proj.valorLiquidoEsperado - (p.investido_centavos ?? 0)
  const usaIndexador = codigo != null && nivelAnual != null
  const nomeIndexador = rotuloIndexador(rf.rate_type, null) ?? "o indexador"
  return (
    <section className="rounded-xl border bg-muted/30 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-sm font-medium">Valor esperado no vencimento</h3>
        <Badge variant="secondary" className="font-normal">
          estimativa
        </Badge>
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              type="button"
              className="text-muted-foreground transition-colors hover:text-foreground"
              aria-label="Como este valor é calculado"
            >
              <Info className="size-3.5" aria-hidden />
            </button>
          </TooltipTrigger>
          <TooltipContent className="max-w-[16rem]">
            <p>
              Juros compostos sobre o valor bruto atual à taxa de{" "}
              {fmtPct.format(proj.taxaAnual * 100)}% a.a.
              {usaIndexador
                ? ` (nível atual de ${nomeIndexador} + spread contratado)`
                : " (taxa contratada)"}
              .
            </p>
            <p className="mt-1">
              {rf.tax_exempt
                ? "Rendimento isento de IR."
                : "Valor já líquido do IR de 15% sobre o lucro (título mantido até o vencimento)."}
            </p>
          </TooltipContent>
        </Tooltip>
      </div>
      <p className="mt-1 text-2xl font-semibold tabular-nums text-accent-ink">
        ≈ {formatBRL(proj.valorLiquidoEsperado)}
      </p>
      <p className="text-xs text-muted-foreground">
        Valor líquido estimado se mantido até o vencimento, sem novos aportes.
      </p>
      <p className="mt-2 flex flex-wrap items-center gap-1 text-xs text-muted-foreground">
        Lucro líquido estimado <Valor centavos={lucro} sinal className="text-xs" />
      </p>
    </section>
  )
}

const PRESETS_TD = [
  { id: "6m", label: "6M" },
  { id: "1a", label: "1A" },
  { id: "2a", label: "2A" },
  { id: "max", label: "Máx" },
] as const

function inicioPresetTD(id: string, compra: string | undefined): string {
  if (id === "6m") return subMeses(hojeISO(), 6)
  if (id === "2a") return subMeses(hojeISO(), 24)
  if (id === "max") return (compra ?? "2000-01-01").slice(0, 10)
  return subMeses(hojeISO(), 12) // 1a (padrão)
}

/** Evolução do investimento em R$ (imagem): valor aplicado e valor bruto da posição, com CDI/IBOV/
 *  IPCA opcionais projetados sobre o capital aplicado inicial p/ compartilhar o eixo em reais.
 *  ponytail: benchmark projeta só o aplicado inicial (não reinveste aportes/resgates da janela);
 *  a linha de valor líquido (após IR) fica para depois — o histórico de IR não é armazenado. */
function EvolucaoInvestimento({ ids, compra }: { ids: number[]; compra: string | undefined }) {
  const [presetId, setPresetId] = useState("1a")
  const inicio = inicioPresetTD(presetId, compra)
  const fim = hojeISO()
  const [selecionados, setSelecionados] = useState<string[]>(["cdi"])
  const indicadores = useIndicadores()
  const serie = usePosicaoSerie(ids, { inicio, fim })
  const pontos = serie.data?.pontos ?? []
  const reconstruidoAte = serie.data?.reconstruido_ate ?? null
  const inicioComum = pontos[0]?.data ?? inicio
  const indicadoresSerie = useIndicadoresSerie(pontos.length >= 2 ? selecionados : [], {
    inicio: inicioComum,
    fim,
  })

  const config: ChartConfig = {
    aplicado: { label: "Valor aplicado", color: "var(--muted-foreground)" },
    bruto: { label: "Valor bruto", color: "var(--primary)" },
  }
  for (const i of indicadores.data ?? [])
    config[i.codigo] = { label: i.nome, color: COR_INDICADOR[i.codigo] ?? "var(--chart-5)" }

  const porData = new Map<string, Record<string, number | string>>()
  for (const pt of pontos)
    porData.set(pt.data, {
      data: pt.data,
      aplicado: pt.investido_centavos,
      bruto: pt.valor_centavos,
    })
  // Benchmark com os MESMOS aportes: o que eu teria se cada aporte tivesse ido para o
  // CDI/SELIC/IPCA/IBOV (comparável em R$ com o valor bruto). Ver `serieBenchmark`.
  const aplicadoAcum = pontos.map((pt) => pt.investido_centavos)
  for (const s of indicadoresSerie.data ?? []) {
    const accPorData = new Map(s.pontos.map((pt) => [pt.data, pt.acumulado_pct / 100]))
    const accIndice: number[] = []
    let acc = 0
    for (const pt of pontos) {
      acc = accPorData.get(pt.data) ?? acc // forward-fill dos dias sem observação
      accIndice.push(acc)
    }
    const valores = serieBenchmark(aplicadoAcum, accIndice)
    pontos.forEach((pt, i) => {
      const linha = porData.get(pt.data)
      if (linha) linha[s.codigo] = valores[i]!
    })
  }
  const dados = [...porData.values()].sort((a, b) => String(a.data).localeCompare(String(b.data)))

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-medium">Evolução do investimento</h3>
        <ToggleGroup
          type="single"
          size="sm"
          variant="outline"
          spacing={0}
          value={presetId}
          onValueChange={(v) => v && setPresetId(v)}
          aria-label="Período"
        >
          {PRESETS_TD.map((pp) => (
            <ToggleGroupItem key={pp.id} value={pp.id}>
              {pp.label}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      </div>

      {indicadores.data && indicadores.data.length > 0 ? (
        <ToggleGroup
          type="multiple"
          size="sm"
          variant="outline"
          spacing={0}
          value={selecionados}
          onValueChange={setSelecionados}
          aria-label="Comparar com"
        >
          {indicadores.data.map((i) => (
            <ToggleGroupItem key={i.codigo} value={i.codigo}>
              {i.nome}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      ) : null}

      {serie.isLoading ? (
        <Skeleton className="h-[240px] w-full" />
      ) : pontos.length < 2 ? (
        <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed px-6 py-10 text-center">
          <ChartLine className="size-6 text-muted-foreground" aria-hidden />
          <p className="text-sm font-medium">O histórico acumula a partir de agora</p>
          <p className="max-w-xs text-xs text-balance text-muted-foreground">
            Cada sincronização grava um ponto diário; a curva aparece conforme os dias passam.
          </p>
        </div>
      ) : (
        <ChartContainer config={config} className="aspect-auto h-[240px] w-full">
          <LineChart data={dados}>
            <CartesianGrid vertical={false} strokeDasharray="3 3" />
            <XAxis
              dataKey="data"
              tickLine={false}
              axisLine={false}
              tickMargin={8}
              minTickGap={32}
              tickFormatter={tickDia}
            />
            <YAxis
              tickLine={false}
              axisLine={false}
              width={52}
              tickFormatter={(v: number) => eixoBRL(Number(v))}
            />
            <ChartTooltip
              content={
                <ChartTooltipContent
                  labelFormatter={(_, payload) =>
                    formatDate(String(payload?.[0]?.payload?.data ?? ""))
                  }
                  formatter={(value, name, item) =>
                    linhaTooltip(value, String(name), item.color, config)
                  }
                />
              }
            />
            <ChartLegend content={<ChartLegendContent />} />
            {reconstruidoAte ? (
              <ReferenceLine
                x={reconstruidoAte}
                stroke="var(--muted-foreground)"
                strokeDasharray="2 4"
                label={{
                  value: "estimado",
                  position: "insideTopLeft",
                  fontSize: 10,
                  fill: "var(--muted-foreground)",
                }}
              />
            ) : null}
            <Line
              dataKey="aplicado"
              stroke="var(--color-aplicado)"
              strokeWidth={1.5}
              strokeDasharray="4 4"
              dot={false}
              isAnimationActive={false}
            />
            <Line
              dataKey="bruto"
              stroke="var(--color-bruto)"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
            {selecionados.map((codigo) => (
              <Line
                key={codigo}
                dataKey={codigo}
                stroke={`var(--color-${codigo})`}
                strokeWidth={1.5}
                strokeDasharray="4 3"
                dot={false}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ChartContainer>
      )}
      <p className="text-xs text-muted-foreground">
        Valores em R$.{" "}
        {reconstruidoAte
          ? `Até ${formatDataISO(reconstruidoAte)} os valores são estimados (capitalização dos aportes pelo indexador realizado; sem marcação a mercado). `
          : ""}
        A linha de valor líquido (após IR) chega em breve.
      </p>
    </section>
  )
}

/** Rótulo de mês (`yyyy-mm` → `jun/25`) p/ o eixo/tooltip do rendimento mensal. */
const rotuloMes = (mes: string) => formatBucketLabel(`${mes}-01`, "mensal")

/** Performance da renda fixa: rendimento **mês a mês** (% de cada mês, não valores em R$) do título vs.
 *  CDI/SELIC/IPCA/IBOV, cada série uma linha. O retorno mensal vem do chain-diff do acumulado
 *  (`retornoMensal`) da série da posição e de cada indicador — sem endpoint novo. Padrão: comparar com
 *  todos os indicadores disponíveis (IBOV só existe com token brapi; `useIndicadores` já o filtra). */
function PerformanceTesouro({ ids, compra }: { ids: number[]; compra: string | undefined }) {
  const [presetId, setPresetId] = useState("1a")
  const inicio = inicioPresetTD(presetId, compra)
  const fim = hojeISO()
  const indicadores = useIndicadores()
  const disponiveis = (indicadores.data ?? []).map((i) => i.codigo)
  // null = ainda no padrão (todos os disponíveis); vira array explícito quando o usuário mexe (inclusive
  // []). Evita esperar a lista assíncrona só p/ pré-selecionar — e não reintroduz IBOV sem token.
  const [selecionados, setSelecionados] = useState<string[] | null>(null)
  const efetivos = selecionados ?? disponiveis

  const serie = usePosicaoSerie(ids, { inicio, fim })
  const mensalAtivo = retornoMensal(serie.data?.pontos ?? [])
  const inicioComum = serie.data?.pontos[0]?.data ?? inicio
  const indicadoresSerie = useIndicadoresSerie(mensalAtivo.length >= 2 ? efetivos : [], {
    inicio: inicioComum,
    fim,
  })

  const config: ChartConfig = { ativo: { label: "Este título", color: "var(--primary)" } }
  for (const i of indicadores.data ?? [])
    config[i.codigo] = { label: i.nome, color: COR_INDICADOR[i.codigo] ?? "var(--chart-5)" }

  const porMes = new Map<string, Record<string, number | string>>()
  for (const m of mensalAtivo) porMes.set(m.mes, { mes: m.mes, ativo: m.pct })
  for (const s of indicadoresSerie.data ?? [])
    for (const m of retornoMensal(s.pontos)) {
      const linha = porMes.get(m.mes)
      if (linha) linha[s.codigo] = m.pct
    }
  const dados = [...porMes.values()].sort((a, b) => String(a.mes).localeCompare(String(b.mes)))

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-medium">Rendimento mensal</h3>
        <ToggleGroup
          type="single"
          size="sm"
          variant="outline"
          spacing={0}
          value={presetId}
          onValueChange={(v) => v && setPresetId(v)}
          aria-label="Período"
        >
          {PRESETS_TD.map((pp) => (
            <ToggleGroupItem key={pp.id} value={pp.id}>
              {pp.label}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      </div>

      {disponiveis.length > 0 ? (
        <ToggleGroup
          type="multiple"
          size="sm"
          variant="outline"
          spacing={0}
          value={efetivos}
          onValueChange={setSelecionados}
          aria-label="Comparar com"
        >
          {(indicadores.data ?? []).map((i) => (
            <ToggleGroupItem key={i.codigo} value={i.codigo}>
              {i.nome}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      ) : null}

      {serie.isLoading ? (
        <Skeleton className="h-[240px] w-full" />
      ) : mensalAtivo.length < 2 ? (
        <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed px-6 py-10 text-center">
          <ChartLine className="size-6 text-muted-foreground" aria-hidden />
          <p className="text-sm font-medium">O rendimento mensal aparece com o tempo</p>
          <p className="max-w-xs text-xs text-balance text-muted-foreground">
            É preciso ao menos dois meses-calendário completos de histórico da posição para comparar o
            rendimento de cada mês.
          </p>
        </div>
      ) : (
        <ChartContainer config={config} className="aspect-auto h-[240px] w-full">
          <LineChart data={dados}>
            <CartesianGrid vertical={false} strokeDasharray="3 3" />
            <XAxis
              dataKey="mes"
              tickLine={false}
              axisLine={false}
              tickMargin={8}
              minTickGap={24}
              tickFormatter={rotuloMes}
            />
            <YAxis
              tickLine={false}
              axisLine={false}
              width={48}
              tickFormatter={(v: number) => pctTexto(v)}
            />
            <ChartTooltip
              content={
                <ChartTooltipContent
                  labelFormatter={(_, payload) => rotuloMes(String(payload?.[0]?.payload?.mes ?? ""))}
                  formatter={(value, name, item) => (
                    <>
                      <span
                        className="mt-0.5 size-2.5 shrink-0 rounded-[2px]"
                        style={{ background: item.color }}
                        aria-hidden
                      />
                      <div className="flex flex-1 items-center justify-between gap-2 leading-none">
                        <span className="text-muted-foreground">
                          {config[String(name)]?.label ?? name}
                        </span>
                        <span className="font-mono font-medium tabular-nums text-foreground">
                          {pctTexto(Number(value))}
                        </span>
                      </div>
                    </>
                  )}
                />
              }
            />
            <ChartLegend content={<ChartLegendContent />} />
            <Line
              dataKey="ativo"
              stroke="var(--color-ativo)"
              strokeWidth={2}
              dot={{ r: 2.5, strokeWidth: 0, fill: "var(--color-ativo)" }}
              isAnimationActive={false}
            />
            {efetivos.map((codigo) => (
              <Line
                key={codigo}
                dataKey={codigo}
                stroke={`var(--color-${codigo})`}
                strokeWidth={1.5}
                strokeDasharray="4 3"
                dot={false}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ChartContainer>
      )}
      <p className="text-xs text-muted-foreground">
        Quanto rendeu em cada mês (%), não valores em R$. O IPCA pode aparecer defasado no mês mais
        recente até a divulgação do IBGE.
      </p>
    </div>
  )
}

const CATEGORIAS = [
  "Compras",
  "Vendas",
  "Transferências",
  "Bonificações",
  "Proventos",
  "Outros",
] as const

function categoriaMovimento(m: InvestimentoTransacao): (typeof CATEGORIAS)[number] {
  const tipo = (m.type ?? "").toUpperCase()
  if (tipo === "BUY") return "Compras"
  if (tipo === "SELL") return "Vendas"
  if (tipo === "TRANSFER") return "Transferências"
  if (tipo === "BONUS" || tipo === "AMORTIZATION") return "Bonificações"
  if (tipo === "DIVIDEND" || tipo === "INTEREST" || m.movement_type === "CREDIT")
    return "Proventos"
  return "Outros"
}

/** Aba Movimentações do FII: totais 12m (cards), gráfico de compras por mês e tabela de negociações.
 *  Mantém o fluxo de aporte manual (adicionar/editar/excluir) integrado à tabela. */
function MovimentacoesFIITab({ ids }: { ids: number[] }) {
  const movimentos = usePosicaoTransacoes(ids)
  const excluir = useExcluirAporte(ids)
  const [form, setForm] = useState<{ aberto: boolean; editar: InvestimentoTransacao | null }>({
    aberto: false,
    editar: null,
  })
  const [excluindo, setExcluindo] = useState<InvestimentoTransacao | null>(null)
  const podeAdicionar = ids.length === 1

  const linhas = movimentos.data ?? []
  const agregado = agregarNegociacoes(linhas, hojeISO())
  const porId = new Map<number, InvestimentoTransacao>(linhas.map((m) => [m.id, m]))

  return (
    <div className="space-y-5">
      {podeAdicionar ? (
        <div className="flex justify-end">
          <Button
            size="sm"
            variant="outline"
            className="gap-1.5"
            onClick={() => setForm({ aberto: true, editar: null })}
          >
            <Plus className="size-4" aria-hidden />
            Adicionar aporte
          </Button>
        </div>
      ) : null}

      {movimentos.isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : agregado.negociacoes.length === 0 ? (
        <EmptyState
          icon={ChartLine}
          title="Sem negociações"
          description="Compras e vendas desta posição aparecem aqui. Adicione seus aportes para calcular o preço médio."
        />
      ) : (
        <>
          <section className="space-y-2">
            <h3 className="text-sm font-medium">Últimos 12 meses</h3>
            <div className="grid grid-cols-2 gap-3">
              <CardTotal titulo="Comprado" total={agregado.compras12m} />
              <CardTotal titulo="Vendido" total={agregado.vendas12m} />
            </div>
          </section>

          <GraficoCompras buckets={agregado.buckets} />

          <TabelaNegociacoes
            negociacoes={agregado.negociacoes}
            podeEditar={podeAdicionar}
            onEditar={(id) => setForm({ aberto: true, editar: porId.get(id) ?? null })}
            onExcluir={(id) => setExcluindo(porId.get(id) ?? null)}
          />
        </>
      )}

      {podeAdicionar ? (
        <AporteDialog
          ids={ids}
          investimentoId={ids[0]}
          editar={form.editar}
          aberto={form.aberto}
          onOpenChange={(aberto) => setForm((f) => ({ ...f, aberto }))}
        />
      ) : null}

      <AlertDialog open={excluindo !== null} onOpenChange={(o) => !o && setExcluindo(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Excluir aporte?</AlertDialogTitle>
            <AlertDialogDescription>
              O aporte sai do cálculo do preço médio e do valor investido. Não dá para desfazer.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (excluindo) excluir.mutate(excluindo.id)
                setExcluindo(null)
              }}
            >
              Excluir
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

/** Card com borda (distinto dos Stat sem borda do topo): total comprado/vendido em 12 meses. */
function CardTotal({ titulo, total }: { titulo: string; total: TotalLado }) {
  return (
    <div className="rounded-lg border p-3">
      <p className="text-xs text-muted-foreground">{titulo}</p>
      <p className="text-lg font-semibold tabular-nums">{formatBRL(total.valor)}</p>
      <p className="text-xs text-muted-foreground">{fmtQtd.format(total.qtd)} cotas</p>
    </div>
  )
}

const CFG_COMPRAS: ChartConfig = {
  valor: { label: "Valor comprado", color: "var(--primary)" },
  qtd: { label: "Quantidade", color: "var(--primary)" },
}

/** Compras dos últimos 12 meses em barras, alternando o total em valor ou em quantidade. */
function GraficoCompras({ buckets }: { buckets: BucketCompra[] }) {
  const [modo, setModo] = useState<"valor" | "qtd">("valor")
  return (
    <section className="space-y-2">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-medium">Compras por mês</h3>
        <ToggleGroup
          type="single"
          size="sm"
          variant="outline"
          spacing={0}
          value={modo}
          onValueChange={(v) => v && setModo(v as "valor" | "qtd")}
        >
          <ToggleGroupItem value="valor">Valor</ToggleGroupItem>
          <ToggleGroupItem value="qtd">Quantidade</ToggleGroupItem>
        </ToggleGroup>
      </div>
      <ChartContainer config={CFG_COMPRAS} className="aspect-auto h-[220px] w-full">
        <BarChart data={buckets}>
          <CartesianGrid vertical={false} strokeDasharray="3 3" />
          <XAxis dataKey="label" tickLine={false} axisLine={false} tickMargin={8} />
          <YAxis
            tickLine={false}
            axisLine={false}
            width={44}
            tickFormatter={modo === "valor" ? eixoBRL : (v) => fmtQtd.format(Number(v))}
          />
          <ChartTooltip
            content={
              <ChartTooltipContent
                formatter={(value, name) => (
                  <div className="flex flex-1 items-center justify-between gap-2 leading-none">
                    <span className="text-muted-foreground">
                      {CFG_COMPRAS[name as string]?.label ?? name}
                    </span>
                    <span className="font-mono font-medium tabular-nums text-foreground">
                      {modo === "valor"
                        ? formatBRL(Number(value))
                        : `${fmtQtd.format(Number(value))} cotas`}
                    </span>
                  </div>
                )}
              />
            }
          />
          <Bar dataKey={modo} fill="var(--primary)" radius={4} />
        </BarChart>
      </ChartContainer>
    </section>
  )
}

/** Histórico de negociações (BUY/SELL): dia, tipo, quantidade, preço da cota e valor total. Aportes
 *  manuais ganham ações de editar/excluir (só em posição de 1 investimento). */
function TabelaNegociacoes({
  negociacoes,
  podeEditar,
  onEditar,
  onExcluir,
}: {
  negociacoes: Negociacao[]
  podeEditar: boolean
  onEditar: (id: number) => void
  onExcluir: (id: number) => void
}) {
  return (
    <section className="space-y-2">
      <h3 className="text-sm font-medium">Histórico de negociações</h3>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Dia</TableHead>
            <TableHead>Tipo</TableHead>
            <TableHead className="text-right">Qtd.</TableHead>
            <TableHead className="text-right">Preço da cota</TableHead>
            <TableHead className="text-right">Valor total</TableHead>
            {podeEditar ? <TableHead className="w-0" aria-label="Ações" /> : null}
          </TableRow>
        </TableHeader>
        <TableBody>
          {negociacoes.map((n) => (
            <TableRow key={n.id}>
              <TableCell>{n.quando ? formatDate(n.quando) : "—"}</TableCell>
              <TableCell>
                <span className="inline-flex items-center gap-1.5">
                  {n.lado === "BUY" ? "Compra" : "Venda"}
                  {n.manual ? (
                    <Badge variant="secondary" className="px-1.5 py-0 text-[10px]">
                      Manual
                    </Badge>
                  ) : null}
                </span>
              </TableCell>
              <TableCell className="text-right tabular-nums">{fmtQtd.format(n.quantidade)}</TableCell>
              <TableCell className="text-right tabular-nums">
                {n.precoCentavos != null ? formatBRL(n.precoCentavos) : "—"}
              </TableCell>
              <TableCell className="text-right tabular-nums">{formatBRL(n.valorCentavos)}</TableCell>
              {podeEditar ? (
                <TableCell className="text-right">
                  {n.manual ? (
                    <div className="flex justify-end gap-1">
                      <Button
                        size="icon"
                        variant="ghost"
                        className="size-7 text-muted-foreground"
                        aria-label="Editar aporte"
                        onClick={() => onEditar(n.id)}
                      >
                        <Pencil className="size-3.5" />
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="size-7 text-muted-foreground"
                        aria-label="Excluir aporte"
                        onClick={() => onExcluir(n.id)}
                      >
                        <Trash2 className="size-3.5" />
                      </Button>
                    </div>
                  ) : null}
                </TableCell>
              ) : null}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </section>
  )
}

/** Movimentações mescladas do grupo, agrupadas por categoria (compras/vendas/transf./bonif./…).
 *  Permite adicionar/editar/excluir aportes manuais (posição de 1 investimento). */
function MovimentacoesTab({ ids }: { ids: number[] }) {
  const movimentos = usePosicaoTransacoes(ids)
  const excluir = useExcluirAporte(ids)
  const [form, setForm] = useState<{ aberto: boolean; editar: InvestimentoTransacao | null }>({
    aberto: false,
    editar: null,
  })
  const [excluindo, setExcluindo] = useState<InvestimentoTransacao | null>(null)
  const podeAdicionar = ids.length === 1

  const linhas = movimentos.data ?? []
  const porCategoria = new Map<string, InvestimentoTransacao[]>()
  for (const m of linhas) {
    const c = categoriaMovimento(m)
    const arr = porCategoria.get(c)
    if (arr) arr.push(m)
    else porCategoria.set(c, [m])
  }

  return (
    <div className="space-y-4">
      {podeAdicionar ? (
        <div className="flex justify-end">
          <Button
            size="sm"
            variant="outline"
            className="gap-1.5"
            onClick={() => setForm({ aberto: true, editar: null })}
          >
            <Plus className="size-4" aria-hidden />
            Adicionar aporte
          </Button>
        </div>
      ) : null}

      {movimentos.isLoading ? (
        <Skeleton className="h-40 w-full" />
      ) : linhas.length === 0 ? (
        <EmptyState
          icon={ChartLine}
          title="Sem movimentações"
          description="Compras, vendas e proventos desta posição aparecem aqui. Adicione seus aportes para calcular o preço médio."
        />
      ) : (
        CATEGORIAS.filter((c) => porCategoria.has(c)).map((c) => (
          <section key={c} className="space-y-1">
            <h3 className="text-sm font-medium">{c}</h3>
            <ul className="divide-y">
              {porCategoria.get(c)!.map((m) => (
                <MovimentoLinha
                  key={m.id}
                  movimento={m}
                  onEditar={m.manual ? () => setForm({ aberto: true, editar: m }) : undefined}
                  onExcluir={m.manual ? () => setExcluindo(m) : undefined}
                />
              ))}
            </ul>
          </section>
        ))
      )}

      {podeAdicionar ? (
        <AporteDialog
          ids={ids}
          investimentoId={ids[0]}
          editar={form.editar}
          aberto={form.aberto}
          onOpenChange={(aberto) => setForm((f) => ({ ...f, aberto }))}
        />
      ) : null}

      <AlertDialog open={excluindo !== null} onOpenChange={(o) => !o && setExcluindo(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Excluir aporte?</AlertDialogTitle>
            <AlertDialogDescription>
              O aporte sai do cálculo do preço médio e do valor investido. Não dá para desfazer.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (excluindo) excluir.mutate(excluindo.id)
                setExcluindo(null)
              }}
            >
              Excluir
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

function MovimentoLinha({
  movimento: m,
  onEditar,
  onExcluir,
}: {
  movimento: InvestimentoTransacao
  onEditar?: () => void
  onExcluir?: () => void
}) {
  const quando = m.date ?? m.trade_date
  return (
    <li className="flex items-center justify-between gap-3 py-1.5 text-sm">
      <div className="min-w-0">
        <p className="flex items-center gap-1.5 truncate">
          {m.type ? (MOVIMENTO_LABEL[m.type] ?? m.type) : "Movimento"}
          {m.manual ? (
            <Badge variant="secondary" className="px-1.5 py-0 text-[10px]">
              Manual
            </Badge>
          ) : null}
          {m.description ? (
            <span className="truncate text-muted-foreground"> · {m.description}</span>
          ) : null}
        </p>
        {quando ? (
          <p className="text-xs text-muted-foreground">{formatDate(quando)}</p>
        ) : null}
      </div>
      <div className="flex shrink-0 items-center gap-1">
        <Valor
          centavos={m.movement_type === "DEBIT" ? -m.amount_centavos : m.amount_centavos}
          sinal
          className="text-sm"
        />
        {onEditar ? (
          <Button
            size="icon"
            variant="ghost"
            className="size-7 text-muted-foreground"
            aria-label="Editar aporte"
            onClick={onEditar}
          >
            <Pencil className="size-3.5" />
          </Button>
        ) : null}
        {onExcluir ? (
          <Button
            size="icon"
            variant="ghost"
            className="size-7 text-muted-foreground"
            aria-label="Excluir aporte"
            onClick={onExcluir}
          >
            <Trash2 className="size-3.5" />
          </Button>
        ) : null}
      </div>
    </li>
  )
}

/** Dialog do aporte manual. O form fica num componente que só monta quando aberto (com `key`),
 *  então os campos já nascem preenchidos p/ edição — sem `useEffect` de sincronização. */
function AporteDialog({
  ids,
  investimentoId,
  editar,
  aberto,
  onOpenChange,
}: {
  ids: number[]
  investimentoId: number
  editar: InvestimentoTransacao | null
  aberto: boolean
  onOpenChange: (aberto: boolean) => void
}) {
  return (
    <Dialog open={aberto} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{editar ? "Editar aporte" : "Adicionar aporte"}</DialogTitle>
          <DialogDescription>
            Informe uma compra que o banco não trouxe. Entra no cálculo do preço médio.
          </DialogDescription>
        </DialogHeader>
        {aberto ? (
          <AporteForm
            key={editar?.id ?? "novo"}
            ids={ids}
            investimentoId={investimentoId}
            editar={editar}
            onPronto={() => onOpenChange(false)}
          />
        ) : null}
      </DialogContent>
    </Dialog>
  )
}

function AporteForm({
  ids,
  investimentoId,
  editar,
  onPronto,
}: {
  ids: number[]
  investimentoId: number
  editar: InvestimentoTransacao | null
  onPronto: () => void
}) {
  const criar = useCriarAporte(ids)
  const editarM = useEditarAporte(ids)
  const [data, setData] = useState(
    editar ? (editar.date ?? editar.trade_date ?? "").slice(0, 10) : hojeISO()
  )
  const [quantidade, setQuantidade] = useState(
    editar?.quantity != null ? String(editar.quantity) : ""
  )
  const [valor, setValor] = useState(editar ? (editar.amount_centavos / 100).toFixed(2) : "")

  const pendente = criar.isPending || editarM.isPending
  function salvar(e: React.FormEvent) {
    e.preventDefault()
    const qtd = Number(quantidade.replace(",", "."))
    const valorCentavos = Math.round(Number(valor.replace(",", ".")) * 100)
    if (!data || !(qtd > 0) || !Number.isFinite(valorCentavos) || valorCentavos < 0) return
    const corpo = { data, quantidade: qtd, valor_centavos: valorCentavos }
    if (editar) editarM.mutate({ aporteId: editar.id, corpo }, { onSuccess: onPronto })
    else criar.mutate({ investimentoId, corpo }, { onSuccess: onPronto })
  }

  return (
    <form className="space-y-4" onSubmit={salvar}>
      <div className="space-y-1.5">
        <label htmlFor="aporte-data" className="text-sm font-medium">
          Data
        </label>
        <Input
          id="aporte-data"
          type="date"
          max={hojeISO()}
          value={data}
          onChange={(e) => setData(e.target.value)}
          required
        />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <label htmlFor="aporte-qtd" className="text-sm font-medium">
            Quantidade
          </label>
          <Input
            id="aporte-qtd"
            inputMode="decimal"
            value={quantidade}
            onChange={(e) => setQuantidade(e.target.value)}
            placeholder="0"
            required
          />
        </div>
        <div className="space-y-1.5">
          <label htmlFor="aporte-valor" className="text-sm font-medium">
            Valor total (R$)
          </label>
          <Input
            id="aporte-valor"
            inputMode="decimal"
            value={valor}
            onChange={(e) => setValor(e.target.value)}
            placeholder="0,00"
            required
          />
        </div>
      </div>
      <DialogFooter>
        <DialogClose asChild>
          <Button type="button" variant="ghost">
            Cancelar
          </Button>
        </DialogClose>
        <Button type="submit" disabled={pendente}>
          Salvar
        </Button>
      </DialogFooter>
    </form>
  )
}

/** Dividendos: histórico + yield do período (FII). Próximos pagamentos: em breve. */
function DividendosTab({ ids }: { ids: number[] }) {
  const [[inicio, fim], setPeriodo] = useState<readonly [string, string]>(
    PRESETS_PERIODO[2].range()
  )
  const proventos = usePosicaoProventos(ids, { inicio, fim })
  const dado = proventos.data
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-medium">Histórico</h3>
        <PeriodoPicker inicio={inicio} fim={fim} onChange={(i, f) => setPeriodo([i, f])} />
      </div>
      {proventos.isLoading || !dado ? (
        <Skeleton className="h-24 w-full" />
      ) : (
        <>
          <div className="flex items-center justify-between rounded-lg bg-primary/5 px-3 py-2 text-sm">
            <span className="text-muted-foreground">
              Total no período{" "}
              {dado.dy_pct != null ? (
                <Badge variant="positive" className="ml-1">
                  Yield {fmtPct.format(dado.dy_pct)}%
                </Badge>
              ) : null}
            </span>
            <Valor centavos={dado.total_centavos} neutro />
          </div>
          {dado.total_isento_centavos > 0 ? (
            <p className="px-1 text-xs text-muted-foreground">
              <Valor centavos={dado.total_isento_centavos} neutro className="text-xs" /> isentos
              de IR (rendimentos do fundo).
            </p>
          ) : null}
          {dado.proventos.length === 0 ? (
            <p className="text-xs text-muted-foreground">Nenhum provento no período.</p>
          ) : (
            <ul className="divide-y">
              {dado.proventos.map((m) => (
                <MovimentoLinha key={m.id} movimento={m} />
              ))}
            </ul>
          )}
        </>
      )}
      <div className="rounded-lg border border-dashed p-3 text-xs text-muted-foreground">
        <span className="font-medium text-foreground">Próximos pagamentos</span> — a agenda de
        proventos futuros chega em breve.
      </div>
    </div>
  )
}

/** Card com borda para o resumo de dividendos (imagem de referência): rótulo + valor forte + sub. */
function CardResumo({
  titulo,
  valor,
  sub,
  destaque,
}: {
  titulo: string
  valor: string
  sub?: string
  destaque?: boolean
}) {
  return (
    <div className="rounded-lg border p-3">
      <p className="text-xs text-muted-foreground">{titulo}</p>
      <p className={cn("text-lg font-semibold tabular-nums", destaque && "text-accent-ink")}>
        {valor}
      </p>
      {sub ? <p className="truncate text-xs text-muted-foreground">{sub}</p> : null}
    </div>
  )
}

const CFG_PROVENTOS: ChartConfig = {
  totalCentavos: { label: "Rendimentos", color: "var(--primary)" },
}

/** Rendimento por cota em reais → `R$ 0,0900`: 4 casas, pois FIIs pagam sub-centavo por cota. */
const fmtRendimentoCota = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  minimumFractionDigits: 4,
  maximumFractionDigits: 4,
})

/** Rendimentos recebidos por mês (12 meses), em barras. */
function GraficoProventos({ buckets }: { buckets: BucketProvento[] }) {
  return (
    <section className="space-y-2">
      <h3 className="text-sm font-medium">Histórico de rendimentos</h3>
      <ChartContainer config={CFG_PROVENTOS} className="aspect-auto h-[220px] w-full">
        <BarChart data={buckets}>
          <CartesianGrid vertical={false} strokeDasharray="3 3" />
          <XAxis dataKey="label" tickLine={false} axisLine={false} tickMargin={8} />
          <YAxis tickLine={false} axisLine={false} width={44} tickFormatter={eixoBRL} />
          <ChartTooltip
            content={
              <ChartTooltipContent
                formatter={(value) => (
                  <div className="flex flex-1 items-center justify-between gap-2 leading-none">
                    <span className="text-muted-foreground">Recebido</span>
                    <span className="font-mono font-medium tabular-nums text-foreground">
                      {formatBRL(Number(value))}
                    </span>
                  </div>
                )}
              />
            }
          />
          <Bar dataKey="totalCentavos" fill="var(--primary)" radius={4} />
        </BarChart>
      </ChartContainer>
    </section>
  )
}

/** Todos os rendimentos recebidos: mês e total recebido (o Pluggy não manda por-cota/cotas em real). */
function TabelaProventos({ linhas }: { linhas: LinhaProvento[] }) {
  return (
    <section className="space-y-2">
      <h3 className="text-sm font-medium">Rendimentos recebidos</h3>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Mês</TableHead>
            <TableHead className="text-right">Total recebido</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {linhas.map((l) => (
            <TableRow key={l.id}>
              <TableCell>{l.label}</TableCell>
              <TableCell className="text-right tabular-nums">{formatBRL(l.totalCentavos)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </section>
  )
}

/** Aba Dividendos do FII: cards de resumo + gráfico de rendimentos por mês + tabela de proventos.
 *  Dados all-time (janela larga); o gráfico recorta os últimos 12 meses em `agregarProventos`. */
function DividendosFIITab({
  posicao,
  fundamentos,
}: {
  posicao: CarteiraPosicao
  fundamentos?: FundamentosFII
}) {
  // "Tudo": 10 anos cobrem o histórico realista de proventos e ficam sob o teto do backend
  // (_MAX_JANELA_DIAS = 3700 ≈ 10,1 anos; 2000-01-01 estourava e dava 422).
  const proventos = usePosicaoProventos(posicao.investimento_ids, {
    inicio: subMeses(hojeISO(), 120),
    fim: hojeISO(),
  })
  const dado = proventos.data

  if (proventos.isLoading || !dado) return <Skeleton className="h-80 w-full" />

  const ag = agregarProventos(dado.proventos, hojeISO())
  if (ag.linhas.length === 0) {
    return (
      <EmptyState
        icon={Receipt}
        title="Sem rendimentos"
        description="Os proventos deste FII aparecem aqui assim que forem sincronizados."
      />
    )
  }

  const dy = fundamentos?.dividend_yield_12m_pct
  const qtd = posicao.quantidade
  // Rendimento por cota do último provento: `value_unitario` quando a API manda; senão total ÷ cotas
  // atuais (o Pluggy não manda por-cota em dados reais). Expectativa = por-cota × cotas atuais.
  const ultimoPorCota =
    ag.ultimoPorCotaReais ??
    (qtd && ag.ultimoTotalCentavos != null ? ag.ultimoTotalCentavos / 100 / qtd : null)
  const expectativa =
    ultimoPorCota != null && qtd != null
      ? formatBRL(Math.round(ultimoPorCota * qtd * 100))
      : "—"

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <CardResumo
          titulo="Dividend Yield (12M)"
          valor={dy != null ? `${fmtPct.format(dy)}%` : "—"}
          destaque
        />
        <CardResumo
          titulo="Último rendimento"
          valor={ultimoPorCota != null ? fmtRendimentoCota.format(ultimoPorCota) : "—"}
          sub={ag.ultimoQuando ? `cota em ${formatDate(ag.ultimoQuando)}` : undefined}
        />
        <CardResumo
          titulo="Expectativa no mês"
          valor={expectativa}
          sub={posicao.quantidade != null ? `${fmtQtd.format(posicao.quantidade)} cotas` : undefined}
        />
        <CardResumo titulo="Total recebido" valor={formatBRL(ag.totalCentavos)} />
      </div>

      <GraficoProventos buckets={ag.buckets} />
      <TabelaProventos linhas={ag.linhas} />
    </div>
  )
}

/** Indicadores do FII (CVM): principais + alocação da carteira. Estado vazio antes da 1ª ingestão. */
function IndicadoresFIITab({ ids }: { ids: number[] }) {
  const q = usePosicaoFundamentos(ids, true)
  const f = q.data
  if (q.isLoading || !f) return <Skeleton className="h-64 w-full" />
  if (!f.disponivel)
    return (
      <EmptyState
        icon={Sparkles}
        title="Fundamentos ainda não sincronizados"
        description="Os dados do fundo (CVM) chegam na próxima atualização — o Informe Mensal é publicado de 15 a 30 dias após o fim do mês."
      />
    )
  const principais = [
    { rotulo: "P/VP", valor: f.pvp != null ? fmtPct.format(f.pvp) : null },
    {
      rotulo: "Dividend Yield (12M)",
      valor: f.dividend_yield_12m_pct != null ? `${fmtPct.format(f.dividend_yield_12m_pct)}%` : null,
    },
    {
      rotulo: "Patrimônio líquido",
      valor: f.patrimonio_liquido_centavos != null ? formatBRL(f.patrimonio_liquido_centavos) : null,
    },
    {
      rotulo: "Nº de cotistas",
      valor: f.num_cotistas != null ? f.num_cotistas.toLocaleString("pt-BR") : null,
    },
    {
      rotulo: "Valor patrim. da cota",
      valor:
        f.valor_patrimonial_cota_centavos != null
          ? formatBRL(f.valor_patrimonial_cota_centavos)
          : null,
    },
    {
      rotulo: "Vacância física",
      valor: f.vacancia_pct != null ? `${fmtPct.format(f.vacancia_pct)}%` : null,
    },
    {
      rotulo: "Inadimplência",
      valor: f.inadimplencia_pct != null ? `${fmtPct.format(f.inadimplencia_pct)}%` : null,
    },
  ].filter((i) => i.valor != null)
  return (
    <div className="space-y-4">
      <section>
        <h3 className="mb-2 text-sm font-medium">Indicadores principais</h3>
        <div className="grid grid-cols-2 gap-2">
          {principais.map((i) => (
            <div key={i.rotulo} className="rounded-lg border bg-background/60 px-3 py-2">
              <p className="text-xs text-muted-foreground">{i.rotulo}</p>
              <p className="font-medium tabular-nums text-accent-ink">{i.valor}</p>
            </div>
          ))}
        </div>
      </section>

      {f.alocacao.length > 0 ? (
        <section>
          <h3 className="mb-2 text-sm font-medium">Alocação da carteira</h3>
          <AlocacaoDonut alocacao={f.alocacao} />
        </section>
      ) : null}

      <div className="flex items-start gap-2 rounded-lg border border-dashed p-3 text-xs text-muted-foreground">
        <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden />
        <span>
          Fonte: CVM{f.data_referencia ? ` · dados de ${formatDate(f.data_referencia)}` : ""}. As
          informações não constituem recomendação de investimento.
        </span>
      </div>
    </div>
  )
}

/** Alocação da carteira do FII (CVM) em rosca — uma fatia por classe de ativo. */
function AlocacaoDonut({ alocacao }: { alocacao: FundamentosFIIAlocacao[] }) {
  const cor = (i: number) => `var(--chart-${(i % 6) + 1})`
  const config: ChartConfig = Object.fromEntries(
    alocacao.map((a, i) => [a.classe, { label: a.classe, color: cor(i) }]),
  )
  return (
    <div className="flex flex-col items-center gap-3">
      <ChartContainer config={config} className="aspect-square h-[180px]">
        <PieChart>
          <ChartTooltip
            content={
              <ChartTooltipContent
                nameKey="classe"
                formatter={(value, name) => (
                  <>
                    <span
                      className="mt-0.5 size-2.5 shrink-0 rounded-[2px]"
                      style={{ background: config[String(name)]?.color }}
                      aria-hidden
                    />
                    <div className="flex flex-1 items-center justify-between gap-2 leading-none">
                      <span className="text-muted-foreground">
                        {config[String(name)]?.label ?? name}
                      </span>
                      <span className="font-mono font-medium tabular-nums text-foreground">
                        {fmtPct.format(Number(value))}%
                      </span>
                    </div>
                  </>
                )}
              />
            }
          />
          <Pie data={alocacao} dataKey="pct" nameKey="classe" innerRadius={45} strokeWidth={2}>
            {alocacao.map((a, i) => (
              <Cell key={a.classe} fill={cor(i)} />
            ))}
          </Pie>
        </PieChart>
      </ChartContainer>
      <ul className="w-full space-y-1.5">
        {alocacao.map((a, i) => (
          <li key={a.classe} className="flex items-center gap-2 text-sm">
            <span
              className="size-2.5 shrink-0 rounded-[2px]"
              style={{ background: cor(i) }}
              aria-hidden
            />
            <span className="truncate">{a.classe}</span>
            <span className="ml-auto shrink-0 tabular-nums text-muted-foreground">
              {fmtPct.format(a.pct)}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

/** Insights: dados do fundo para apoiar a análise. O mango não faz recomendações de investimento. */
function InsightsTab() {
  return (
    <div className="space-y-3">
      <EmBreve
        titulo="Insights para sua análise"
        descricao="Reunimos os indicadores e dados do fundo para apoiar suas decisões. O mango não faz recomendações de investimento."
      />
    </div>
  )
}

function EmBreve({ titulo, descricao }: { titulo: string; descricao: string }) {
  return <EmptyState icon={Sparkles} title={titulo} description={descricao} />
}
