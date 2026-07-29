import {
  AlertTriangle,
  ChartLine,
  ChevronDown,
  Coins,
  FolderInput,
  Landmark,
  Layers,
  Pencil,
  TrendingDown,
  TrendingUp,
} from "lucide-react"
import type { LucideIcon } from "lucide-react"
import { useState } from "react"
import { Link } from "react-router"
import { CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts"

import { PeriodoPicker } from "@/components/dashboard/periodo-picker"
import { EmptyState } from "@/components/common/empty-state"
import { Valor } from "@/components/common/valor"
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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import {
  ToggleGroup,
  ToggleGroupItem,
} from "@/components/ui/toggle-group"
import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart"
import { useMe } from "@/lib/api/auth"
import { useIndicadores, useIndicadoresSerie } from "@/lib/api/indicadores"
import {
  useAtivos,
  useCarteiraResumo,
  useCarteiraSerie,
  useCriarAtivo,
  useInvestimento,
  useInvestimentoTransacoes,
  useProventosFII,
  useRenomearAtivo,
  useVincularAtivo,
  type CarteiraAtivoRF,
  type CarteiraAtivoRV,
  type CarteiraItem,
  type CarteiraResumo,
  type InvestimentoTransacao,
  type RecorteCarteira,
} from "@/lib/api/investimentos"
import { addDias, formatBRL, formatDate, hojeISO, subMeses } from "@/lib/format"
import { ilustracao } from "@/lib/illustrations"
import {
  ICONE_TIPO,
  iconeTipo,
  rotuloSubtype,
  rotuloTipo,
} from "@/lib/investimento-taxonomia"

// --- vocabulário (taxonomia do Pluggy → pt-BR) --------------------------------------------------

const MOVIMENTO_LABEL: Record<string, string> = {
  BUY: "Aplicação",
  SELL: "Resgate",
  DIVIDEND: "Provento",
  TRANSFER: "Transferência",
  TAX: "Imposto/taxa",
  AMORTIZATION: "Amortização",
}

const fmtQtd = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 8 })
const fmtPct = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 })
/** Percentual com sinal explícito — cor nunca é o único portador de sentido (a11y). */
const pctTexto = (v: number) => `${v > 0 ? "+" : ""}${fmtPct.format(v)}%`
const fmtDiaMes = new Intl.DateTimeFormat("pt-BR", {
  day: "2-digit",
  month: "2-digit",
})
const tickDia = (iso: string) => fmtDiaMes.format(new Date(`${iso}T12:00:00`))

export function InvestimentosPage() {
  const resumo = useCarteiraResumo()
  const [detalheId, setDetalheId] = useState<number | null>(null)

  if (resumo.isError) {
    return (
      <EmptyState
        icon={AlertTriangle}
        title="Não foi possível carregar a carteira"
        description="Tente novamente em instantes."
      />
    )
  }
  if (resumo.isLoading || !resumo.data) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-9 w-64" />
        <div className="grid gap-4 lg:grid-cols-2">
          <Skeleton className="h-[420px] w-full" />
          <Skeleton className="h-[420px] w-full" />
        </div>
      </div>
    )
  }

  const dados = resumo.data
  if (dados.totais.quantidade_ativos === 0) {
    return (
      <div className="space-y-6">
        <CabecalhoPagina />
        <EmptyState
          icon={TrendingUp}
          title="Nenhum investimento importado"
          description="Conecte uma conta com investimentos pelo Pluggy e sincronize — a carteira chega pronta, com valores e impostos já calculados."
        >
          <Button asChild>
            <Link to="/configuracoes">Conectar conta</Link>
          </Button>
        </EmptyState>
      </div>
    )
  }

  // Renda variável (por code) e renda fixa (por ativo) têm seções próprias; o resto vai em grupos.
  const gruposRestantes = dados.grupos.filter(
    (g) => g.type !== "EQUITY" && g.type !== "ETF" && g.type !== "FIXED_INCOME"
  )

  return (
    <div className="space-y-6">
      <CabecalhoPagina />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <CardTotalCarteira totais={dados.totais} />
        <Card>
          <CardHeader className="pb-0">
            <CardTitle className="text-base">Alocação por tipo</CardTitle>
          </CardHeader>
          <CardContent>
            <AlocacaoPorTipo itens={dados.alocacao} />
          </CardContent>
        </Card>
      </div>

      {dados.renda_variavel.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Renda variável por ativo</CardTitle>
            <CardDescription>
              Total investido, valor atual e valorização de cada ativo
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-1">
            {dados.renda_variavel.map((ativo) => (
              <AtivoLinha
                key={ativo.code}
                ativo={ativo}
                onAbrir={() => setDetalheId(ativo.investimento_ids[0])}
              />
            ))}
          </CardContent>
        </Card>
      ) : null}

      {dados.renda_fixa.length > 0 ? (
        <RendaFixaSection ativos={dados.renda_fixa} onAbrir={setDetalheId} />
      ) : null}

      {gruposRestantes.map((grupo) => (
        <Card key={grupo.type}>
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle className="text-base">{rotuloTipo(grupo.type)}</CardTitle>
            <Valor centavos={grupo.valor_centavos} neutro className="text-sm" />
          </CardHeader>
          <CardContent className="space-y-1">
            {grupo.itens.map((item) => (
              <InvestimentoLinha
                key={item.id}
                item={item}
                onAbrir={() => setDetalheId(item.id)}
              />
            ))}
          </CardContent>
        </Card>
      ))}

      <ComparacaoMercado subtypes={dados.alocacao.map((a) => a.tipo)} />

      <InvestimentoDetalheDialog
        id={detalheId}
        onFechar={() => setDetalheId(null)}
      />
    </div>
  )
}

function CabecalhoPagina() {
  return (
    <header className="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold">Investimentos</h1>
        <p className="text-sm text-muted-foreground">
          Carteira importada do Open Finance — valores e impostos já calculados.
        </p>
      </div>
      <SyncButton />
    </header>
  )
}

/** Card do valor da carteira: número + mascote e, por baixo, os chips de fato
 *  (investido / resultado / ativos) — mesmo padrão do total de assinaturas. */
function CardTotalCarteira({ totais }: { totais: CarteiraResumo["totais"] }) {
  const me = useMe()
  const resultado = totais.resultado_centavos
  return (
    <Card className="relative gap-0 overflow-hidden py-0">
      {/* decorativos → ilustração → dados (empilhamento de trás p/ frente) */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-gradient-to-br from-primary/15 via-primary/5 to-transparent"
      />
      <CardContent className="relative flex flex-col gap-4 p-4 sm:p-5">
        <div className="relative z-10">
          <p className="text-sm font-medium text-muted-foreground">
            Valor da carteira
          </p>
          <Valor
            centavos={totais.valor_centavos}
            neutro
            className="text-4xl font-bold md:text-5xl"
          />
        </div>
        <div className="flex h-64 items-end justify-center">
          <img
            src={ilustracao(me.data?.avatar, "money")}
            alt=""
            className="pointer-events-none h-full max-w-full object-contain"
          />
        </div>
        <div className="grid grid-cols-3 gap-2 sm:gap-2.5">
          <StatChip
            icon={Coins}
            valor={
              <Valor
                centavos={totais.investido_centavos ?? 0}
                neutro
                className="text-sm font-bold sm:text-lg"
              />
            }
            rotulo="investido"
          />
          <StatChip
            icon={
              resultado != null && resultado < 0 ? TrendingDown : TrendingUp
            }
            valor={
              resultado != null ? (
                <Valor
                  centavos={resultado}
                  sinal
                  className="text-sm font-bold sm:text-lg"
                />
              ) : (
                <span className="text-sm font-bold sm:text-lg">—</span>
              )
            }
            rotulo={
              totais.resultado_pct != null
                ? `resultado (${pctTexto(totais.resultado_pct)})`
                : "resultado"
            }
          />
          <StatChip
            icon={Layers}
            valor={
              <span className="text-sm font-bold tabular-nums sm:text-lg">
                {totais.quantidade_ativos}
              </span>
            }
            rotulo={totais.quantidade_ativos === 1 ? "ativo" : "ativos"}
          />
        </div>
      </CardContent>
    </Card>
  )
}

function StatChip({
  icon: Icon,
  valor,
  rotulo,
}: {
  icon: LucideIcon
  valor: React.ReactNode
  rotulo: string
}) {
  return (
    <div className="rounded-xl border border-border/60 bg-background/70 p-2.5 backdrop-blur-sm sm:p-3">
      <span
        aria-hidden
        className="grid size-8 place-items-center rounded-lg bg-primary/10 text-primary"
      >
        <Icon className="size-4" />
      </span>
      <div className="mt-2 leading-tight">{valor}</div>
      <p className="text-xs text-muted-foreground">{rotulo}</p>
    </div>
  )
}

/** Bar-list da alocação: ícone do tipo, nome + barra proporcional e valor + (%). */
function AlocacaoPorTipo({ itens }: { itens: CarteiraResumo["alocacao"] }) {
  const maximo = Math.max(...itens.map((a) => a.valor_centavos), 0)
  return (
    <div className="space-y-1">
      {itens.map((a) => {
        const Icone = iconeTipo(a.tipo)
        const largura = maximo > 0 ? (a.valor_centavos / maximo) * 100 : 0
        return (
          <div
            key={a.tipo}
            className="grid grid-cols-[auto_1fr_auto] items-center gap-3 rounded-lg px-2 py-2"
          >
            <span
              aria-hidden
              className="grid size-9 place-items-center rounded-lg bg-primary/10 text-primary"
            >
              <Icone className="size-4.5" />
            </span>
            <div className="min-w-0">
              <p className="truncate text-sm font-medium">
                {rotuloSubtype(a.tipo) ?? rotuloTipo(a.tipo)}
              </p>
              <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-primary/10">
                <div
                  className="h-full rounded-full bg-primary"
                  style={{ width: `${largura}%` }}
                />
              </div>
            </div>
            <span className="text-sm whitespace-nowrap tabular-nums">
              {formatBRL(a.valor_centavos)}{" "}
              <span className="text-muted-foreground">
                ({Math.round(a.pct)}%)
              </span>
            </span>
          </div>
        )
      })}
    </div>
  )
}

function AtivoLinha({
  ativo,
  onAbrir,
}: {
  ativo: CarteiraAtivoRV
  onAbrir: () => void
}) {
  return (
    <button
      type="button"
      onClick={onAbrir}
      className="grid w-full grid-cols-[auto_1fr_auto] items-center gap-3 rounded-lg px-2 py-2 text-left transition-colors hover:bg-muted/60"
    >
      <span
        aria-hidden
        className="grid size-9 place-items-center rounded-lg bg-primary/10 font-mono text-[0.6rem] font-bold text-primary"
      >
        {ativo.code.slice(0, 4)}
      </span>
      <div className="min-w-0">
        <p className="truncate text-sm font-medium">{ativo.code}</p>
        <p className="truncate text-xs text-muted-foreground">
          {ativo.quantidade != null
            ? `${fmtQtd.format(ativo.quantidade)} cota${ativo.quantidade === 1 ? "" : "s"}`
            : (ativo.nome ?? "")}
          {ativo.preco_medio_centavos != null
            ? ` · preço médio ${formatBRL(ativo.preco_medio_centavos)}`
            : ""}
        </p>
      </div>
      <div className="text-right">
        <Valor centavos={ativo.valor_centavos} neutro className="text-sm" />
        {ativo.valorizacao_centavos != null ? (
          <p className="text-xs">
            <Valor
              centavos={ativo.valorizacao_centavos}
              sinal
              className="text-xs"
            />
            {ativo.valorizacao_pct != null ? (
              <span className="text-muted-foreground">
                {" "}
                ({pctTexto(ativo.valorizacao_pct)})
              </span>
            ) : null}
          </p>
        ) : null}
      </div>
    </button>
  )
}

function InvestimentoLinha({
  item,
  onAbrir,
}: {
  item: CarteiraItem
  onAbrir: () => void
}) {
  const Icone = ICONE_TIPO[item.subtype ?? item.type] ?? Coins
  const meta = [
    rotuloSubtype(item.subtype),
    item.due_date ? `vence ${formatDate(item.due_date)}` : null,
    item.last_twelve_months_rate != null
      ? `${fmtPct.format(item.last_twelve_months_rate)}% em 12m`
      : null,
  ]
    .filter(Boolean)
    .join(" · ")
  return (
    <button
      type="button"
      onClick={onAbrir}
      className="grid w-full grid-cols-[auto_1fr_auto] items-center gap-3 rounded-lg px-2 py-2 text-left transition-colors hover:bg-muted/60"
    >
      <span
        aria-hidden
        className="grid size-9 place-items-center rounded-lg bg-primary/10 text-primary"
      >
        <Icone className="size-4.5" />
      </span>
      <div className="min-w-0">
        <p className="truncate text-sm font-medium">{item.nome ?? item.code}</p>
        {meta ? (
          <p className="truncate text-xs text-muted-foreground">{meta}</p>
        ) : null}
      </div>
      <div className="text-right">
        <Valor centavos={item.valor_centavos} neutro className="text-sm" />
        {item.resultado_centavos != null ? (
          <p className="text-xs">
            <Valor
              centavos={item.resultado_centavos}
              sinal
              className="text-xs"
            />
            {item.resultado_pct != null ? (
              <span className="text-muted-foreground">
                {" "}
                ({pctTexto(item.resultado_pct)})
              </span>
            ) : null}
          </p>
        ) : null}
      </div>
    </button>
  )
}

// --- renda fixa por ativo (§4.9) ----------------------------------------------------------------

/** Compras do mesmo papel agrupadas num ativo; resultado do ativo = soma das partes. Cada ativo
 *  expande p/ ver as compras, renomear (lápis) e mover uma compra p/ outro ativo. */
function RendaFixaSection({
  ativos,
  onAbrir,
}: {
  ativos: CarteiraAtivoRF[]
  onAbrir: (id: number) => void
}) {
  const [renomear, setRenomear] = useState<CarteiraAtivoRF | null>(null)
  const [mover, setMover] = useState<CarteiraItem | null>(null)
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Renda fixa por ativo</CardTitle>
        <CardDescription>
          Compras do mesmo papel agrupadas — o resultado é a soma das partes
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-1">
        {ativos.map((a) => (
          <AtivoRFItem
            key={a.ativo_id ?? `avulso-${a.investimento_ids[0]}`}
            ativo={a}
            onAbrir={onAbrir}
            onRenomear={() => setRenomear(a)}
            onMover={setMover}
          />
        ))}
      </CardContent>
      <RenomearAtivoDialog ativo={renomear} onFechar={() => setRenomear(null)} />
      <MoverAtivoDialog posicao={mover} onFechar={() => setMover(null)} />
    </Card>
  )
}

function AtivoRFItem({
  ativo,
  onAbrir,
  onRenomear,
  onMover,
}: {
  ativo: CarteiraAtivoRF
  onAbrir: (id: number) => void
  onRenomear: () => void
  onMover: (p: CarteiraItem) => void
}) {
  const resultado = ativo.resultado_centavos
  const n = ativo.investimento_ids.length
  return (
    <details className="group rounded-lg [&_summary]:list-none">
      <summary className="grid cursor-pointer grid-cols-[auto_1fr_auto] items-center gap-3 rounded-lg px-2 py-2 transition-colors hover:bg-muted/60">
        <span
          aria-hidden
          className="grid size-9 place-items-center rounded-lg bg-primary/10 text-primary"
        >
          <Landmark className="size-4.5" />
        </span>
        <div className="min-w-0">
          <p className="truncate text-sm font-medium">{ativo.nome ?? "Renda fixa"}</p>
          <p className="truncate text-xs text-muted-foreground">
            {n} compra{n === 1 ? "" : "s"}
          </p>
        </div>
        <div className="flex items-center gap-1">
          <div className="text-right">
            <Valor centavos={ativo.valor_centavos} neutro className="text-sm" />
            {resultado != null ? (
              <p className="text-xs">
                <Valor centavos={resultado} sinal className="text-xs" />
                {ativo.resultado_pct != null ? (
                  <span className="text-muted-foreground">
                    {" "}
                    ({pctTexto(ativo.resultado_pct)})
                  </span>
                ) : null}
              </p>
            ) : null}
          </div>
          {ativo.ativo_id != null ? (
            <Button
              variant="ghost"
              size="icon"
              className="shrink-0"
              onClick={(e) => {
                e.preventDefault()
                onRenomear()
              }}
              aria-label="Renomear ativo"
            >
              <Pencil className="size-4" />
            </Button>
          ) : null}
          <ChevronDown
            className="size-4 text-muted-foreground transition-transform group-open:rotate-180"
            aria-hidden
          />
        </div>
      </summary>
      <div className="space-y-1 pt-1 pl-2">
        {ativo.posicoes.map((p) => (
          <div key={p.id} className="flex items-center gap-1">
            <div className="min-w-0 flex-1">
              <InvestimentoLinha item={p} onAbrir={() => onAbrir(p.id)} />
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="shrink-0"
              onClick={() => onMover(p)}
              aria-label="Mover compra para outro ativo"
            >
              <FolderInput className="size-4" />
            </Button>
          </div>
        ))}
      </div>
    </details>
  )
}

function RenomearAtivoDialog({
  ativo,
  onFechar,
}: {
  ativo: CarteiraAtivoRF | null
  onFechar: () => void
}) {
  return (
    <Dialog open={ativo != null} onOpenChange={(a) => !a && onFechar()}>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>Renomear ativo</DialogTitle>
          <DialogDescription>
            Um nome que agrupe as compras deste papel.
          </DialogDescription>
        </DialogHeader>
        {/* key remonta com estado fresco a cada ativo (evita setState em efeito) */}
        {ativo?.ativo_id != null ? (
          <RenomearForm key={ativo.ativo_id} ativo={ativo} onFechar={onFechar} />
        ) : null}
      </DialogContent>
    </Dialog>
  )
}

function RenomearForm({
  ativo,
  onFechar,
}: {
  ativo: CarteiraAtivoRF
  onFechar: () => void
}) {
  const renomear = useRenomearAtivo()
  const [nome, setNome] = useState(ativo.nome ?? "")
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        const limpo = nome.trim()
        if (ativo.ativo_id != null && limpo)
          renomear.mutate({ id: ativo.ativo_id, nome: limpo }, { onSuccess: onFechar })
      }}
      className="flex gap-2"
    >
      <Input
        value={nome}
        onChange={(e) => setNome(e.target.value)}
        autoFocus
        maxLength={255}
        placeholder="Ex.: Tesouro Selic 2028"
      />
      <Button type="submit" disabled={!nome.trim() || renomear.isPending}>
        Salvar
      </Button>
    </form>
  )
}

function MoverAtivoDialog({
  posicao,
  onFechar,
}: {
  posicao: CarteiraItem | null
  onFechar: () => void
}) {
  return (
    <Dialog open={posicao != null} onOpenChange={(a) => !a && onFechar()}>
      <DialogContent className="flex max-h-[calc(100dvh-2rem)] flex-col gap-0 sm:max-w-sm">
        <DialogHeader className="shrink-0 pb-3">
          <DialogTitle>Mover compra</DialogTitle>
          <DialogDescription className="truncate">
            {posicao?.nome ?? posicao?.code ?? ""}
          </DialogDescription>
        </DialogHeader>
        {posicao != null ? (
          <MoverConteudo key={posicao.id} posicao={posicao} onFechar={onFechar} />
        ) : null}
      </DialogContent>
    </Dialog>
  )
}

function MoverConteudo({
  posicao,
  onFechar,
}: {
  posicao: CarteiraItem
  onFechar: () => void
}) {
  const ativos = useAtivos()
  const vincular = useVincularAtivo()
  const criar = useCriarAtivo()
  const [novo, setNovo] = useState("")

  const mover = (ativoId: number | null) =>
    vincular.mutate({ investimentoId: posicao.id, ativoId }, { onSuccess: onFechar })
  const criarEMover = () => {
    const nome = novo.trim()
    if (!nome) return
    criar.mutate(nome, {
      onSuccess: (a) =>
        vincular.mutate(
          { investimentoId: posicao.id, ativoId: a.id },
          { onSuccess: onFechar }
        ),
    })
  }
  return (
    <>
      <div className="min-h-0 space-y-1 overflow-y-auto">
        {(ativos.data ?? []).map((a) => (
          <button
            key={a.id}
            type="button"
            onClick={() => mover(a.id)}
            className="flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-sm transition-colors hover:bg-muted/60"
          >
            <Landmark className="size-4 shrink-0 text-muted-foreground" aria-hidden />
            <span className="truncate">{a.nome}</span>
          </button>
        ))}
        <button
          type="button"
          onClick={() => mover(null)}
          className="flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-sm text-muted-foreground transition-colors hover:bg-muted/60"
        >
          Deixar sem ativo (avulsa)
        </button>
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault()
          criarEMover()
        }}
        className="mt-3 flex shrink-0 gap-2 border-t pt-3"
      >
        <Input
          value={novo}
          onChange={(e) => setNovo(e.target.value)}
          maxLength={255}
          placeholder="Criar novo ativo…"
        />
        <Button
          type="submit"
          variant="secondary"
          disabled={!novo.trim() || criar.isPending || vincular.isPending}
        >
          Criar
        </Button>
      </form>
    </>
  )
}

// --- comparação com o mercado (§4.9) ------------------------------------------------------------

const PRESETS_PERIODO = [
  {
    id: "30d",
    label: "30 dias",
    range: () => [addDias(hojeISO(), -29), hojeISO()] as const,
  },
  {
    id: "3m",
    label: "3 meses",
    range: () => [subMeses(hojeISO(), 3), hojeISO()] as const,
  },
  {
    id: "6m",
    label: "6 meses",
    range: () => [subMeses(hojeISO(), 6), hojeISO()] as const,
  },
  {
    id: "12m",
    label: "12 meses",
    range: () => [subMeses(hojeISO(), 12), hojeISO()] as const,
  },
]

const COR_INDICADOR: Record<string, string> = {
  cdi: "var(--chart-2)",
  selic: "var(--chart-3)",
  ipca: "var(--chart-4)",
  ibov: "var(--chart-5)",
}

function ComparacaoMercado({ subtypes }: { subtypes: string[] }) {
  const [[inicio, fim], setPeriodo] = useState<readonly [string, string]>(
    PRESETS_PERIODO[1].range()
  )
  const [recorte, setRecorte] = useState<RecorteCarteira>("todos")
  const [subtype, setSubtype] = useState<string | null>(null)
  const [selecionados, setSelecionados] = useState<string[]>(["cdi"])

  const indicadores = useIndicadores()
  const serie = useCarteiraSerie({ recorte, subtype, inicio, fim })
  const pontos = serie.data?.pontos ?? []
  // Indicadores rebased no 1º dia com dado da carteira — % acumulado na mesma base.
  const inicioComum = pontos[0]?.data ?? inicio
  const indicadoresSerie = useIndicadoresSerie(
    pontos.length >= 2 ? selecionados : [],
    { inicio: inicioComum, fim }
  )

  const config: ChartConfig = {
    carteira: { label: "Carteira", color: "var(--primary)" },
  }
  for (const i of indicadores.data ?? []) {
    config[i.codigo] = {
      label: i.nome,
      color: COR_INDICADOR[i.codigo] ?? "var(--chart-5)",
    }
  }

  const porData = new Map<string, Record<string, number | string>>()
  for (const p of pontos) {
    porData.set(p.data, { data: p.data, carteira: p.acumulado_pct })
  }
  for (const s of indicadoresSerie.data ?? []) {
    for (const p of s.pontos) {
      const linha = porData.get(p.data)
      if (linha) linha[s.codigo] = p.acumulado_pct
    }
  }
  const dadosChart = [...porData.values()].sort((a, b) =>
    String(a.data).localeCompare(String(b.data))
  )

  const presetAtivo =
    PRESETS_PERIODO.find((p) => {
      const [i, f] = p.range()
      return i === inicio && f === fim
    })?.id ?? ""

  return (
    <Card>
      <CardHeader className="gap-3">
        <div className="flex flex-wrap items-end justify-between gap-2">
          <div>
            <CardTitle className="text-base">
              Comparação com o mercado
            </CardTitle>
            <CardDescription>
              Rentabilidade acumulada da carteira contra os indicadores
              escolhidos
            </CardDescription>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <ToggleGroup
              type="single"
              size="sm"
              variant="outline"
              spacing={0}
              value={presetAtivo}
              onValueChange={(v) => {
                const p = PRESETS_PERIODO.find((x) => x.id === v)
                if (p) setPeriodo(p.range())
              }}
            >
              {PRESETS_PERIODO.map((p) => (
                <ToggleGroupItem key={p.id} value={p.id}>
                  {p.label}
                </ToggleGroupItem>
              ))}
            </ToggleGroup>
            <PeriodoPicker
              inicio={inicio}
              fim={fim}
              onChange={(i, f) => setPeriodo([i, f])}
            />
          </div>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <ToggleGroup
              type="single"
              size="sm"
              variant="outline"
              spacing={0}
              value={subtype ? "" : recorte}
              onValueChange={(v) => {
                if (!v) return
                setRecorte(v as RecorteCarteira)
                setSubtype(null)
              }}
              aria-label="Recorte da carteira"
            >
              <ToggleGroupItem value="todos">Carteira</ToggleGroupItem>
              <ToggleGroupItem value="renda_fixa">Renda fixa</ToggleGroupItem>
              <ToggleGroupItem value="renda_variavel">
                Renda variável
              </ToggleGroupItem>
            </ToggleGroup>
            <Select
              value={subtype ?? "todos"}
              onValueChange={(v) => setSubtype(v === "todos" ? null : v)}
            >
              <SelectTrigger
                size="sm"
                className="w-44"
                aria-label="Tipo de ativo"
              >
                <SelectValue placeholder="Por tipo" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="todos">Todos os tipos</SelectItem>
                {subtypes.map((s) => (
                  <SelectItem key={s} value={s}>
                    {rotuloSubtype(s) ?? s}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <ToggleGroup
            type="multiple"
            size="sm"
            variant="outline"
            spacing={0}
            value={selecionados}
            onValueChange={(v) => setSelecionados(v)}
            aria-label="Indicadores"
          >
            {(indicadores.data ?? []).map((i) => (
              <ToggleGroupItem key={i.codigo} value={i.codigo}>
                {i.nome}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
        </div>
      </CardHeader>
      <CardContent>
        {serie.isLoading ? (
          <Skeleton className="h-[280px] w-full" />
        ) : pontos.length < 2 ? (
          <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed px-6 py-12 text-center">
            <ChartLine className="size-6 text-muted-foreground" aria-hidden />
            <p className="text-sm font-medium">
              O histórico da carteira acumula a partir de agora
            </p>
            <p className="max-w-md text-xs text-balance text-muted-foreground">
              Cada sincronização grava um ponto diário. Em alguns dias a
              comparação com os indicadores aparece aqui; ativos de bolsa com
              ticker ganham o passado pelo preço de mercado.
            </p>
          </div>
        ) : (
          <ChartContainer
            config={config}
            className="aspect-auto h-[280px] w-full"
          >
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
                width={52}
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
                dataKey="carteira"
                stroke="var(--color-carteira)"
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
      </CardContent>
    </Card>
  )
}

// --- detalhe do investimento --------------------------------------------------------------------

function InvestimentoDetalheDialog({
  id,
  onFechar,
}: {
  id: number | null
  onFechar: () => void
}) {
  const inv = useInvestimento(id)
  const movimentos = useInvestimentoTransacoes(id)
  const dado = inv.data

  return (
    <Dialog open={id != null} onOpenChange={(aberto) => !aberto && onFechar()}>
      {/* corpo rolável entre header fixo (padrão de dialog mobile do projeto) */}
      <DialogContent className="flex max-h-[calc(100dvh-2rem)] flex-col gap-0 sm:max-w-lg">
        <DialogHeader className="shrink-0 pb-4">
          <DialogTitle className="flex flex-wrap items-center gap-2">
            {dado?.nome ?? dado?.code ?? "Investimento"}
            {dado?.subtype ? (
              <Badge variant="secondary">{rotuloSubtype(dado.subtype)}</Badge>
            ) : null}
          </DialogTitle>
          <DialogDescription>
            {dado?.instituicao_emissora_nome ??
              (dado ? rotuloTipo(dado.type) : "Carregando…")}
          </DialogDescription>
        </DialogHeader>

        <div className="min-h-0 space-y-5 overflow-y-auto">
          {inv.isLoading || !dado ? (
            <Skeleton className="h-48 w-full" />
          ) : (
            <>
              <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
                <CampoValor
                  rotulo="Valor atual"
                  centavos={dado.amount_centavos ?? dado.saldo_centavos}
                />
                <CampoValor
                  rotulo="Investido"
                  centavos={dado.amount_original_centavos}
                />
                {dado.amount_profit_centavos != null ? (
                  <div>
                    <dt className="text-xs text-muted-foreground">Resultado</dt>
                    <dd>
                      <Valor centavos={dado.amount_profit_centavos} sinal />
                    </dd>
                  </div>
                ) : null}
                <CampoValor
                  rotulo="IR provisionado"
                  centavos={dado.taxes_centavos}
                />
                <CampoValor rotulo="IOF" centavos={dado.taxes2_centavos} />
                <CampoValor
                  rotulo="Disponível p/ resgate"
                  centavos={dado.amount_withdrawal_centavos}
                />
                {dado.quantity != null ? (
                  <div>
                    <dt className="text-xs text-muted-foreground">
                      Quantidade
                    </dt>
                    <dd className="tabular-nums">
                      {fmtQtd.format(Number(dado.quantity))}
                      {dado.value_unitario != null
                        ? ` × ${formatBRL(Math.round(Number(dado.value_unitario) * 100))}`
                        : ""}
                    </dd>
                  </div>
                ) : null}
                {dado.rate != null ? (
                  <div>
                    <dt className="text-xs text-muted-foreground">Taxa</dt>
                    <dd className="tabular-nums">
                      {fmtPct.format(Number(dado.rate))}%
                      {dado.rate_type ? ` ${dado.rate_type}` : ""}
                    </dd>
                  </div>
                ) : null}
                {dado.fixed_annual_rate != null ? (
                  <div>
                    <dt className="text-xs text-muted-foreground">
                      Taxa anual
                    </dt>
                    <dd className="tabular-nums">
                      {fmtPct.format(Number(dado.fixed_annual_rate))}% a.a.
                    </dd>
                  </div>
                ) : null}
                {dado.last_twelve_months_rate != null ? (
                  <div>
                    <dt className="text-xs text-muted-foreground">
                      Rentab. 12 meses
                    </dt>
                    <dd className="tabular-nums">
                      {fmtPct.format(Number(dado.last_twelve_months_rate))}%
                    </dd>
                  </div>
                ) : null}
                {dado.due_date ? (
                  <div>
                    <dt className="text-xs text-muted-foreground">
                      Vencimento
                    </dt>
                    <dd>{formatDate(dado.due_date)}</dd>
                  </div>
                ) : null}
              </dl>

              {dado.subtype === "REAL_ESTATE_FUND" ? (
                <ProventosBloco id={dado.id} />
              ) : null}

              <MovimentosBloco movimentos={movimentos.data ?? []} />
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}

function CampoValor({
  rotulo,
  centavos,
}: {
  rotulo: string
  centavos: number | null | undefined
}) {
  if (centavos == null) return null
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{rotulo}</dt>
      <dd>
        <Valor centavos={centavos} neutro />
      </dd>
    </div>
  )
}

/** Proventos + dividend yield do período (§4.9 FII) — números prontos do servidor. */
function ProventosBloco({ id }: { id: number }) {
  const [[inicio, fim], setPeriodo] = useState<readonly [string, string]>(
    PRESETS_PERIODO[3].range() // 12 meses
  )
  const proventos = useProventosFII(id, { inicio, fim })
  return (
    <section className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-medium">Proventos</h3>
        <PeriodoPicker
          inicio={inicio}
          fim={fim}
          onChange={(i, f) => setPeriodo([i, f])}
        />
      </div>
      {proventos.isLoading || !proventos.data ? (
        <Skeleton className="h-16 w-full" />
      ) : (
        <>
          <div className="flex items-center justify-between rounded-lg bg-primary/5 px-3 py-2 text-sm">
            <span className="text-muted-foreground">
              Total no período{" "}
              {proventos.data.dy_pct != null ? (
                <Badge variant="positive" className="ml-1">
                  DY {fmtPct.format(proventos.data.dy_pct)}%
                </Badge>
              ) : null}
            </span>
            <Valor centavos={proventos.data.total_centavos} neutro />
          </div>
          {proventos.data.total_isento_centavos > 0 ? (
            <p className="px-3 text-xs text-muted-foreground">
              <Valor
                centavos={proventos.data.total_isento_centavos}
                neutro
                className="text-xs"
              />{" "}
              isentos de IR (rendimentos do fundo)
            </p>
          ) : null}
          {proventos.data.proventos.length === 0 ? (
            <p className="text-xs text-muted-foreground">
              Nenhum provento no período.
            </p>
          ) : (
            <ul className="space-y-1">
              {proventos.data.proventos.map((p) => (
                <MovimentoLinha key={p.id} movimento={p} />
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  )
}

function MovimentosBloco({
  movimentos,
}: {
  movimentos: InvestimentoTransacao[]
}) {
  if (movimentos.length === 0) return null
  return (
    <section className="space-y-2">
      <h3 className="text-sm font-medium">Movimentos</h3>
      <ul className="space-y-1">
        {movimentos.map((m) => (
          <MovimentoLinha key={m.id} movimento={m} />
        ))}
      </ul>
    </section>
  )
}

function MovimentoLinha({
  movimento: m,
}: {
  movimento: InvestimentoTransacao
}) {
  const quando = m.date ?? m.trade_date
  return (
    <li className="flex items-center justify-between gap-3 py-1 text-sm">
      <div className="min-w-0">
        <p className="truncate">
          {m.type ? (MOVIMENTO_LABEL[m.type] ?? m.type) : "Movimento"}
          {m.description ? (
            <span className="text-muted-foreground"> · {m.description}</span>
          ) : null}
        </p>
        {quando ? (
          <p className="text-xs text-muted-foreground">{formatDate(quando)}</p>
        ) : null}
      </div>
      <Valor
        centavos={
          m.movement_type === "DEBIT" ? -m.amount_centavos : m.amount_centavos
        }
        sinal
        className="shrink-0 text-sm"
      />
    </li>
  )
}
