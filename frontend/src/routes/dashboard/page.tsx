import {
  DndContext,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core"
import {
  SortableContext,
  arrayMove,
  rectSortingStrategy,
  useSortable,
} from "@dnd-kit/sortable"
import { CSS } from "@dnd-kit/utilities"
import {
  AlertTriangle,
  ArrowDown,
  ArrowRight,
  ArrowUp,
  EyeOff,
  GripVertical,
  Landmark,
  LayoutGrid,
  MoveHorizontal,
  Plus,
  RotateCcw,
} from "lucide-react"
import { useMemo, useState, type ReactNode } from "react"
import { Link } from "react-router"
import { toast } from "sonner"

import { EmptyState } from "@/components/common/empty-state"
import { Valor } from "@/components/common/valor"
import {
  BarrasEmpilhadasCategorias,
  DistribuicaoCategorias,
  GraficoFluxo,
  GraficoPatrimonio,
  RoscaEntradasSaidas,
} from "@/components/dashboard/graficos"
import { KpiCard } from "@/components/dashboard/kpi-card"
import { PeriodoPicker } from "@/components/dashboard/periodo-picker"
import { SyncButton } from "@/components/sync-button"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Skeleton } from "@/components/ui/skeleton"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { useCategorias, nomeCategoria } from "@/lib/api/categorias"
import { useContas } from "@/lib/api/contas"
import {
  useDashboard,
  useDashboardSeries,
  usePatrimonio,
  type Granularidade,
} from "@/lib/api/dashboard"
import { useAtualizarPerfil, usePerfil } from "@/lib/api/perfil"
import {
  CATALOGO,
  ROTULO_LARGURA,
  layoutPadrao,
  mesclarLayout,
  mesmoLayout,
  mover,
  proximaLargura,
  type Largura,
  type WidgetId,
  type WidgetLayout,
} from "@/lib/dashboard-layout"
import {
  addDias,
  formatDate,
  hojeISO,
  mesAteHoje,
  mesmoPeriodoMesAnterior,
  subMeses,
  ultimos6MesesCompletos,
} from "@/lib/format"
import { cn } from "@/lib/utils"

const PERIODO_LABEL: Record<Granularidade, string> = {
  diaria: "dia",
  semanal: "semana",
  mensal: "mês",
}

/** Presets do filtro rápido: intervalo até hoje (fuso SP). */
const PRESETS_RAPIDOS = [
  {
    id: "7d",
    label: "7 dias",
    range: () => [addDias(hojeISO(), -6), hojeISO()] as const,
  },
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
]

// Classes estáticas (o Tailwind não enxerga classe montada em runtime). Grid de 60 no `lg`; abaixo
// dele 2 colunas: até ½ ocupa uma, mais largo ocupa as duas; no mobile (1 coluna) tudo é inteiro.
const SPAN: Record<Largura, string> = {
  12: "sm:col-span-1 lg:col-span-12",
  15: "sm:col-span-1 lg:col-span-15",
  20: "sm:col-span-1 lg:col-span-20",
  30: "sm:col-span-1 lg:col-span-30",
  40: "sm:col-span-2 lg:col-span-40",
  45: "sm:col-span-2 lg:col-span-45",
  60: "sm:col-span-2 lg:col-span-60",
}

const TITULO = new Map(CATALOGO.map((w) => [w.id as string, w.titulo]))

/** Variação relativa vs. período anterior; `null` quando não há base de comparação. */
function variacao(atual: number, anterior: number | undefined): number | null {
  if (anterior == null || anterior === 0) return null
  return (atual - anterior) / Math.abs(anterior)
}

export function DashboardPage() {
  // Cards "no mês": sempre mês corrente até hoje, comparados ao mesmo período do mês anterior.
  const mes = mesAteHoje()
  const dashMes = useDashboard(mes)
  const dashMesAnterior = useDashboard(
    mesmoPeriodoMesAnterior(mes.inicio, mes.fim)
  )
  // Tendência dos cards: mesma métrica nos últimos 6 meses completos (uma query compartilhada).
  const tendencia = useDashboardSeries(ultimos6MesesCompletos(), "mensal")
  const buckets6m = tendencia.data?.buckets ?? []

  // Seletor de período: manda nos gráficos de período, não nos cards "no mês" nem no patrimônio.
  const [inicio, setInicio] = useState(mes.inicio)
  const [fim, setFim] = useState(mes.fim)
  const periodo = { inicio, fim }
  const rotuloPeriodo = `${formatDate(inicio)} a ${formatDate(fim)}`

  const [granFluxo, setGranFluxo] = useState<Granularidade>("semanal")
  const serieFluxo = useDashboardSeries(periodo, granFluxo)
  const [granCat, setGranCat] = useState<Granularidade>("semanal")
  const serieCat = useDashboardSeries(periodo, granCat)
  const dashPeriodo = useDashboard(periodo)
  const patrimonio = usePatrimonio(12)

  const contas = useContas()
  const categorias = useCategorias()
  // Estável entre renders: os gráficos memorizam a option por ela (hover não pode resetar).
  const rotulo = useMemo(
    () =>
      new Map(
        (categorias.data ?? []).map((c) => [c.pluggy_id, nomeCategoria(c)])
      ),
    [categorias.data]
  )

  // Personalização: rascunho só existe no modo edição; salva no perfil ao concluir.
  const perfil = usePerfil()
  const salvar = useAtualizarPerfil()
  const salvo = useMemo(
    () => mesclarLayout(perfil.data?.dashboard_layout as WidgetLayout[] | null),
    [perfil.data?.dashboard_layout]
  )
  const [rascunho, setRascunho] = useState<WidgetLayout[] | null>(null)
  const editando = rascunho !== null
  const layout = rascunho ?? salvo
  const visiveis = layout.filter((w) => w.visivel)
  const ocultos = layout.filter((w) => !w.visivel)

  const sensores = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } })
  )

  function concluir() {
    if (!rascunho) return
    if (mesmoLayout(rascunho, salvo)) {
      setRascunho(null)
      return
    }
    // Igual ao padrão → null: o usuário acompanha mudanças futuras do padrão.
    const valor = mesmoLayout(rascunho, layoutPadrao()) ? null : rascunho
    salvar.mutate(
      { dashboard_layout: valor },
      {
        onSuccess: () => setRascunho(null),
        onError: (e) => toast.error(e.message),
      }
    )
  }

  function alterar(id: string, f: (w: WidgetLayout) => WidgetLayout) {
    setRascunho((r) => (r ?? salvo).map((w) => (w.id === id ? f(w) : w)))
  }

  function moverVisivel(id: string, delta: number) {
    // ▲/▼ andam entre os visíveis; os ocultos mantêm a posição relativa na lista completa.
    setRascunho((r) => {
      const base = r ?? salvo
      const ids = base.filter((w) => w.visivel).map((w) => w.id)
      const alvo = mover(ids, ids.indexOf(id), delta)
      const fila = alvo.map((i) => base.find((w) => w.id === i)!)
      return base.map((w) => (w.visivel ? fila.shift()! : w))
    })
  }

  function aoSoltar(e: DragEndEvent) {
    if (!e.over || e.active.id === e.over.id) return
    setRascunho((r) => {
      const base = r ?? salvo
      const de = base.findIndex((w) => w.id === e.active.id)
      const para = base.findIndex((w) => w.id === e.over!.id)
      return arrayMove(base, de, para)
    })
  }

  // Sem contas conectadas: ensina o próximo passo em vez de mostrar zeros.
  if (contas.isSuccess && contas.data.length === 0) {
    return (
      <EmptyState
        icon={Landmark}
        title="Conecte o Open Finance para começar"
        description="Assim que você conectar uma conta pelo Pluggy, o painel mostra entradas, saídas e resumos do período."
      >
        <Button asChild>
          <Link to="/configuracoes">Conectar conta</Link>
        </Button>
      </EmptyState>
    )
  }

  const ant = dashMesAnterior.data
  const d = dashMes.data

  function kpi(
    label: string,
    centavos: (r: NonNullable<typeof d>) => number,
    extra?: Partial<Parameters<typeof KpiCard>[0]>
  ) {
    if (dashMes.isError) return <ErroCard />
    if (!d) return <Skeleton className="h-full min-h-36 w-full rounded-xl" />
    return <KpiCard label={label} centavos={centavos(d)} {...extra} />
  }

  const widgets: Record<WidgetId, () => ReactNode> = {
    "kpi-saldo": () => kpi("Saldo em contas", (r) => r.saldo_total_centavos),
    "kpi-entradas": () =>
      kpi("Entradas no mês", (r) => r.entradas_centavos, {
        sinal: true,
        delta: d && variacao(d.entradas_centavos, ant?.entradas_centavos),
        serie: buckets6m,
        campo: "entradas_centavos",
      }),
    "kpi-saidas": () =>
      kpi("Saídas no mês", (r) => -r.saidas_centavos, {
        delta: d && variacao(d.saidas_centavos, ant?.saidas_centavos),
        serie: buckets6m,
        campo: "saidas_centavos",
      }),
    "kpi-resultado": () =>
      kpi("Resultado no mês", (r) => r.resultado_centavos, {
        sinal: true,
        delta: d && variacao(d.resultado_centavos, ant?.resultado_centavos),
        serie: buckets6m,
        campo: "resultado_centavos",
      }),
    "kpi-investido": () =>
      kpi("Investido no mês", (r) => r.investido_centavos, {
        sinal: true,
        delta: d && variacao(d.investido_centavos, ant?.investido_centavos),
        serie: buckets6m,
        campo: "investido_centavos",
      }),
    fluxo: () => (
      <CardGrafico
        titulo="Entradas e saídas"
        descricao={`Por ${PERIODO_LABEL[granFluxo]} · ${rotuloPeriodo}`}
        acao={
          <SeletorGranularidade valor={granFluxo} onChange={setGranFluxo} />
        }
      >
        {serieFluxo.isLoading ? (
          <Skeleton className="h-[280px] w-full" />
        ) : (
          <GraficoFluxo
            buckets={serieFluxo.data?.buckets ?? []}
            granularidade={granFluxo}
          />
        )}
      </CardGrafico>
    ),
    categorias: () => (
      <CardGrafico
        titulo="Despesas por categoria"
        descricao={`Todas as despesas · ${rotuloPeriodo} (sem transferências e investimentos)`}
        acao={<SeletorGranularidade valor={granCat} onChange={setGranCat} />}
      >
        <div className="space-y-8">
          {/* Distribuição: total do período inteiro (não depende da granularidade). */}
          {dashPeriodo.isLoading ? (
            <Skeleton className="h-[260px] w-full" />
          ) : (
            <DistribuicaoCategorias
              gastos={dashPeriodo.data?.gasto_por_categoria ?? []}
              rotulo={rotulo}
            />
          )}
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground">
              Por {PERIODO_LABEL[granCat]}
            </p>
            {serieCat.isLoading ? (
              <Skeleton className="h-[240px] w-full" />
            ) : (
              <BarrasEmpilhadasCategorias
                buckets={serieCat.data?.buckets ?? []}
                granularidade={granCat}
                rotulo={rotulo}
                comLegenda={false}
              />
            )}
          </div>
        </div>
      </CardGrafico>
    ),
    patrimonio: () => (
      <CardGrafico
        titulo="Evolução patrimonial"
        descricao="Contas e investimentos no fim de cada mês, últimos 12 meses (cartões fora)"
      >
        {patrimonio.isLoading ? (
          <Skeleton className="h-[280px] w-full" />
        ) : patrimonio.isError ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            Não foi possível carregar o patrimônio.
          </p>
        ) : (
          <GraficoPatrimonio pontos={patrimonio.data ?? []} />
        )}
      </CardGrafico>
    ),
    consolidado: () => (
      <CardGrafico
        titulo="Período consolidado"
        descricao={`Entradas e saídas · ${rotuloPeriodo}`}
      >
        {dashPeriodo.isLoading ? (
          <Skeleton className="h-[160px] w-full" />
        ) : (
          <RoscaEntradasSaidas
            entradas={dashPeriodo.data?.entradas_centavos ?? 0}
            saidas={dashPeriodo.data?.saidas_centavos ?? 0}
          />
        )}
      </CardGrafico>
    ),
    faturas: () => (
      <CardGrafico
        titulo="Faturas em aberto"
        descricao="Próximos vencimentos"
        acao={
          <Button asChild variant="ghost" size="sm">
            <Link to="/faturas">Ver faturas</Link>
          </Button>
        }
      >
        {!d ? (
          <Skeleton className="h-20 w-full" />
        ) : d.faturas_abertas.length === 0 ? (
          <p className="py-4 text-sm text-muted-foreground">
            Nenhuma fatura a vencer.
          </p>
        ) : (
          <div className="space-y-1">
            {d.faturas_abertas.map((f) => (
              <Link
                key={f.id}
                to={`/faturas/${f.id}`}
                className="flex items-center justify-between gap-3 rounded-md py-1.5 text-sm transition-colors hover:text-primary"
              >
                <span>Vencimento {formatDate(f.due_date)}</span>
                <Valor centavos={-f.total_amount_centavos} />
              </Link>
            ))}
          </div>
        )}
      </CardGrafico>
    ),
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <FiltrosRapidos
            inicio={inicio}
            fim={fim}
            onChange={(i, f) => {
              setInicio(i)
              setFim(f)
            }}
          />
          <PeriodoPicker
            inicio={inicio}
            fim={fim}
            onChange={(i, f) => {
              setInicio(i)
              setFim(f)
            }}
          />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {editando ? (
            <>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={ocultos.length === 0}
                  >
                    <Plus aria-hidden />
                    Adicionar visualização
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="min-w-56">
                  <DropdownMenuLabel>Visualizações ocultas</DropdownMenuLabel>
                  {ocultos.map((w) => (
                    <DropdownMenuItem
                      key={w.id}
                      onSelect={() =>
                        alterar(w.id, (x) => ({ ...x, visivel: true }))
                      }
                    >
                      {TITULO.get(w.id)}
                    </DropdownMenuItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setRascunho(layoutPadrao())}
              >
                <RotateCcw aria-hidden />
                Restaurar padrão
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setRascunho(null)}
              >
                Cancelar
              </Button>
              <Button size="sm" onClick={concluir} disabled={salvar.isPending}>
                {salvar.isPending ? "Salvando…" : "Concluir"}
              </Button>
            </>
          ) : (
            <>
              <SyncButton />
              <Button
                variant="outline"
                size="sm"
                onClick={() => setRascunho(salvo)}
              >
                <LayoutGrid aria-hidden />
                Personalizar
              </Button>
            </>
          )}
        </div>
      </div>

      {editando ? (
        <p className="rounded-lg bg-muted/60 px-4 py-2.5 text-sm text-muted-foreground">
          Arraste os blocos pela alça ou use ▲ ▼ para reordenar. Cada bloco pode
          ser ocultado e, em telas largas, mudar de largura; os ocultos voltam
          por “Adicionar visualização”.
        </p>
      ) : null}

      {d && d.nao_revisadas > 0 ? (
        <Link
          to="/transacoes?pendente=true"
          className="flex items-center justify-between rounded-lg border border-dashed bg-muted/40 px-4 py-3 text-sm transition-colors hover:bg-muted"
        >
          <span>
            <strong>{d.nao_revisadas}</strong> transação(ões) aguardando revisão
          </span>
          <ArrowRight className="size-4 text-muted-foreground" aria-hidden />
        </Link>
      ) : null}

      <DndContext
        sensors={sensores}
        collisionDetection={closestCenter}
        onDragEnd={aoSoltar}
      >
        <SortableContext
          items={visiveis.map((w) => w.id)}
          strategy={rectSortingStrategy}
        >
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-60">
            {visiveis.map((w, i) => (
              <Widget
                key={w.id}
                w={w}
                editando={editando}
                primeiro={i === 0}
                ultimo={i === visiveis.length - 1}
                onOcultar={() =>
                  alterar(w.id, (x) => ({ ...x, visivel: false }))
                }
                onLargura={() =>
                  alterar(w.id, (x) => ({
                    ...x,
                    largura: proximaLargura(x.largura),
                  }))
                }
                onMover={(delta) => moverVisivel(w.id, delta)}
              >
                {widgets[w.id as WidgetId]()}
              </Widget>
            ))}
          </div>
        </SortableContext>
      </DndContext>
      {visiveis.length === 0 ? (
        <EmptyState
          icon={LayoutGrid}
          title="Nenhuma visualização no painel"
          description="Use “Adicionar visualização” para trazer os blocos de volta."
        />
      ) : null}
    </div>
  )
}

/** Moldura de um widget: largura no grid e, no modo edição, a barra de controles. */
function Widget({
  w,
  editando,
  primeiro,
  ultimo,
  onOcultar,
  onLargura,
  onMover,
  children,
}: {
  w: WidgetLayout
  editando: boolean
  primeiro: boolean
  ultimo: boolean
  onOcultar: () => void
  onLargura: () => void
  onMover: (delta: number) => void
  children: ReactNode
}) {
  const titulo = TITULO.get(w.id) ?? w.id
  const {
    attributes,
    listeners,
    setNodeRef,
    setActivatorNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: w.id, disabled: !editando })
  return (
    <section
      ref={setNodeRef}
      aria-label={titulo}
      style={{ transform: CSS.Translate.toString(transform), transition }}
      className={cn(
        "relative min-w-0 [&>*]:h-full",
        SPAN[w.largura],
        editando &&
          "rounded-xl outline-2 outline-offset-2 outline-primary/35 outline-dashed",
        isDragging && "z-20 opacity-80"
      )}
    >
      {children}
      {editando ? (
        <div className="absolute -top-3 right-3 z-10 flex h-auto! items-center gap-0.5 rounded-lg border bg-popover p-0.5 shadow-sm">
          <Button
            ref={setActivatorNodeRef}
            variant="ghost"
            size="icon-sm"
            className="cursor-grab touch-none active:cursor-grabbing"
            aria-label={`Arrastar ${titulo}`}
            {...attributes}
            {...listeners}
          >
            <GripVertical aria-hidden />
          </Button>
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={`Ocultar ${titulo}`}
            onClick={onOcultar}
          >
            <EyeOff aria-hidden />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="hidden gap-1 px-2 lg:inline-flex"
            aria-label={`Largura de ${titulo}: ${ROTULO_LARGURA[w.largura]}. Alterar`}
            onClick={onLargura}
          >
            <MoveHorizontal aria-hidden />
            <span className="text-xs tabular-nums">
              {ROTULO_LARGURA[w.largura]}
            </span>
          </Button>
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={`Mover ${titulo} para cima`}
            disabled={primeiro}
            onClick={() => onMover(-1)}
          >
            <ArrowUp aria-hidden />
          </Button>
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={`Mover ${titulo} para baixo`}
            disabled={ultimo}
            onClick={() => onMover(1)}
          >
            <ArrowDown aria-hidden />
          </Button>
        </div>
      ) : null}
    </section>
  )
}

function CardGrafico({
  titulo,
  descricao,
  acao,
  children,
}: {
  titulo: string
  descricao?: string
  acao?: ReactNode
  children: ReactNode
}) {
  return (
    <Card>
      <CardHeader className="flex-row flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="min-w-0">
          <CardTitle className="text-base">{titulo}</CardTitle>
          {descricao ? <CardDescription>{descricao}</CardDescription> : null}
        </div>
        {acao}
      </CardHeader>
      <CardContent className="@container">{children}</CardContent>
    </Card>
  )
}

function ErroCard() {
  return (
    <Card>
      <CardContent className="flex items-center gap-2 text-sm text-muted-foreground">
        <AlertTriangle className="size-4" aria-hidden />
        Não foi possível carregar.
      </CardContent>
    </Card>
  )
}

function SeletorGranularidade({
  valor,
  onChange,
}: {
  valor: Granularidade
  onChange: (g: Granularidade) => void
}) {
  return (
    <ToggleGroup
      type="single"
      size="sm"
      variant="outline"
      spacing={0}
      value={valor}
      onValueChange={(v) => v && onChange(v as Granularidade)}
    >
      <ToggleGroupItem value="diaria">Diário</ToggleGroupItem>
      <ToggleGroupItem value="semanal">Semanal</ToggleGroupItem>
      <ToggleGroupItem value="mensal">Mensal</ToggleGroupItem>
    </ToggleGroup>
  )
}

function FiltrosRapidos({
  inicio,
  fim,
  onChange,
}: {
  inicio: string
  fim: string
  onChange: (inicio: string, fim: string) => void
}) {
  // Preset ativo derivado do período atual — nenhum destaca quando o range é custom.
  const ativo =
    PRESETS_RAPIDOS.find((p) => {
      const [i, f] = p.range()
      return i === inicio && f === fim
    })?.id ?? ""
  return (
    <ToggleGroup
      type="single"
      size="sm"
      variant="outline"
      spacing={0}
      value={ativo}
      onValueChange={(v) => {
        const p = PRESETS_RAPIDOS.find((x) => x.id === v)
        if (p) onChange(...p.range())
      }}
    >
      {PRESETS_RAPIDOS.map((p) => (
        <ToggleGroupItem key={p.id} value={p.id}>
          {p.label}
        </ToggleGroupItem>
      ))}
    </ToggleGroup>
  )
}
