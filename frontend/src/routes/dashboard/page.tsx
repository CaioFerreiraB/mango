import { arrayMove } from "@dnd-kit/sortable"
import {
  ArrowRight,
  Eye,
  EyeOff,
  Landmark,
  LayoutGrid,
  Plus,
  RotateCcw,
  SlidersHorizontal,
} from "lucide-react"
import { useMemo, useState, type ReactNode } from "react"
import { Link, useSearchParams } from "react-router"
import { toast } from "sonner"

import { EmptyState } from "@/components/common/empty-state"
import { PageHeader } from "@/components/common/page-header"
import { AbaDespesas, AbaReceitas } from "@/components/dashboard/abas-analise"
import {
  DespesasFixasMesWidget,
  DespesasFixasProximosWidget,
} from "@/components/dashboard/despesas-fixas-widget"
import { CalendarioCalor } from "@/components/dashboard/calendario-calor"
import { GradeWidgets } from "@/components/dashboard/grade-widgets"
import {
  CardGrafico,
  ErroCard,
  SeletorGranularidade,
} from "@/components/dashboard/card-grafico"
import {
  GraficoFluxo,
  GraficoPatrimonio,
} from "@/components/dashboard/graficos"
import { KpiCard, SaldoDestaque } from "@/components/dashboard/kpi-card"
import { TransacoesTabela } from "@/components/transacoes/transacoes-tabela"
import { PeriodoPicker } from "@/components/dashboard/periodo-picker"
import {
  Drawer,
  DrawerClose,
  DrawerContent,
  DrawerDescription,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
  DrawerTrigger,
} from "@/components/ui/drawer"
import { SyncButton } from "@/components/sync-button"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { useCategorias, nomeCategoria } from "@/lib/api/categorias"
import { useContas, useSaldoContasSerie } from "@/lib/api/contas"
import {
  useDashboard,
  useDashboardSeries,
  usePatrimonio,
  PERIODO_LABEL,
  type Granularidade,
  type Visao,
} from "@/lib/api/dashboard"
import {
  useAtualizarPerfil,
  usePerfil,
  type PerfilUpdate,
} from "@/lib/api/perfil"
import { useTransacoes } from "@/lib/api/transacoes"
import {
  CATALOGO,
  abaDe,
  layoutPadrao,
  mesclarLayout,
  mesmoLayout,
  mover,
  restaurarAba,
  type Aba,
  type WidgetLayout,
} from "@/lib/dashboard-layout"
import {
  addDias,
  formatBucketLabel,
  formatDate,
  hojeISO,
  mesAteHoje,
  mesmoPeriodoMesAnterior,
  subMeses,
  ultimos6MesesCompletos,
} from "@/lib/format"

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

const TITULO = new Map(CATALOGO.map((w) => [w.id as string, w.titulo]))

/** Variação relativa vs. período anterior; `null` quando não há base de comparação. */
function variacao(atual: number, anterior: number | undefined): number | null {
  if (anterior == null || anterior === 0) return null
  return (atual - anterior) / Math.abs(anterior)
}

const CHAVE_OCULTO = "mango:dashboard-oculto"
const CHAVE_VISAO = "mango:dashboard-visao"

const ABAS: Aba[] = ["geral", "receitas", "despesas"]

export function DashboardPage() {
  // Competência × caixa: vale para KPIs, gráficos e abas. Lembrado neste navegador.
  const [visao, setVisao] = useState<Visao>(() => {
    try {
      return localStorage.getItem(CHAVE_VISAO) === "caixa"
        ? "caixa"
        : "competencia"
    } catch {
      return "competencia"
    }
  })
  const trocarVisao = (v: Visao) => {
    setVisao(v)
    try {
      localStorage.setItem(CHAVE_VISAO, v)
    } catch {
      // armazenamento bloqueado (aba privada): vale só nesta visita
    }
  }
  // Cards "no mês": sempre mês corrente até hoje, comparados ao mesmo período do mês anterior.
  const mes = mesAteHoje()
  const dashMes = useDashboard(mes, visao)
  const dashMesAnterior = useDashboard(
    mesmoPeriodoMesAnterior(mes.inicio, mes.fim),
    visao
  )
  // Tendência dos cards: mesma métrica nos últimos 6 meses completos (uma query compartilhada).
  const tendencia = useDashboardSeries(
    ultimos6MesesCompletos(),
    "mensal",
    visao
  )
  const buckets6m = tendencia.data?.buckets ?? []

  // Seletor de período: manda nos gráficos de período, não nos cards "no mês" nem no patrimônio.
  const [inicio, setInicio] = useState(mes.inicio)
  const [fim, setFim] = useState(mes.fim)
  const periodo = { inicio, fim }
  const mudarPeriodo = (i: string, f: string) => {
    setInicio(i)
    setFim(f)
  }
  const rotuloPeriodo = `${formatDate(inicio)} a ${formatDate(fim)}`

  const [granFluxo, setGranFluxo] = useState<Granularidade>("semanal")
  const serieFluxo = useDashboardSeries(periodo, granFluxo, visao)
  // Aba na URL (?aba=receitas): o voltar do navegador e um link direto funcionam.
  const [params, setParams] = useSearchParams()
  const aba = ABAS.includes(params.get("aba") as Aba)
    ? (params.get("aba") as Aba)
    : "geral"
  const trocarAba = (v: string) =>
    setParams(
      (p) => {
        if (v === "geral") p.delete("aba")
        else p.set("aba", v)
        return p
      },
      { replace: true }
    )
  const patrimonio = usePatrimonio(12)
  // Mesmo recorte padrão da tela de transações (sem pagamento de fatura nem parcelas futuras).
  const ultimas = useTransacoes({
    ocultar_pagamento_fatura: true,
    ocultar_futuras: true,
    limit: 10,
  })

  const contas = useContas()
  const saldoSerie = useSaldoContasSerie()
  // Modo privacidade dos cards: o olho mora no topo e vale para as três abas.
  // Lembrado neste navegador — quem esconde os valores não quer vê-los voltar ao recarregar.
  const [oculto, setOculto] = useState(() => {
    try {
      return localStorage.getItem(CHAVE_OCULTO) === "1"
    } catch {
      return false
    }
  })
  const alternarOculto = () => {
    setOculto(!oculto)
    try {
      localStorage.setItem(CHAVE_OCULTO, oculto ? "0" : "1")
    } catch {
      // armazenamento bloqueado (aba privada): vale só nesta visita
    }
  }
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
  // Cada aba lê só os seus widgets da lista comum (ver dashboard-layout).
  const daAba = layout.filter((w) => abaDe(w.id) === aba)
  const visiveis = daAba.filter((w) => w.visivel)
  const ocultos = daAba.filter((w) => !w.visivel)

  function concluir() {
    if (!rascunho) return
    if (mesmoLayout(rascunho, salvo)) {
      setRascunho(null)
      return
    }
    // Igual ao padrão → null: o usuário acompanha mudanças futuras do padrão.
    const valor = mesmoLayout(rascunho, layoutPadrao()) ? null : rascunho
    salvar.mutate(
      // Largura vem das frações do catálogo (LARGURAS), as mesmas que o backend aceita.
      { dashboard_layout: valor as PerfilUpdate["dashboard_layout"] },
      {
        onSuccess: () => setRascunho(null),
        onError: (e) => toast.error(e.message),
      }
    )
  }

  function alterar(id: string, patch: Partial<WidgetLayout>) {
    setRascunho((r) =>
      (r ?? salvo).map((w) => {
        if (w.id !== id) return w
        const novo = { ...w, ...patch }
        // Altura automática = sem a chave (o layout salvo não carrega `altura: undefined`).
        if (novo.altura === undefined) delete novo.altura
        return novo
      })
    )
  }

  function moverVisivel(id: string, delta: number) {
    // ▲/▼ andam entre os visíveis da aba; os demais mantêm a posição na lista completa.
    setRascunho((r) => {
      const base = r ?? salvo
      const daVez = (w: WidgetLayout) => w.visivel && abaDe(w.id) === aba
      const ids = base.filter(daVez).map((w) => w.id)
      const alvo = mover(ids, ids.indexOf(id), delta)
      const fila = alvo.map((i) => base.find((w) => w.id === i)!)
      return base.map((w) => (daVez(w) ? fila.shift()! : w))
    })
  }

  function reordenar(de: string, para: string) {
    setRascunho((r) => {
      const base = r ?? salvo
      return arrayMove(
        base,
        base.findIndex((w) => w.id === de),
        base.findIndex((w) => w.id === para)
      )
    })
  }

  // Grade de qualquer aba: mesma edição, sobre os widgets que a aba entrega.
  const grade = (widgets: Record<string, () => ReactNode>) => (
    <GradeWidgets
      itens={visiveis}
      widgets={widgets}
      editando={editando}
      bloqueado={salvar.isPending}
      onAlterar={alterar}
      onMover={moverVisivel}
      onReordenar={reordenar}
    />
  )

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
    return (
      <KpiCard
        label={label}
        centavos={centavos(d)}
        oculto={oculto}
        {...extra}
      />
    )
  }

  const pendentes =
    d && d.nao_revisadas > 0 ? (
      <Link
        to="/transacoes?pendente=true"
        className="group flex items-center gap-3 rounded-lg bg-muted/70 px-4 py-3 text-sm transition-colors hover:bg-muted"
      >
        <span className="size-2 shrink-0 rounded-full bg-warning" aria-hidden />
        <span className="flex-1">
          <strong>{d.nao_revisadas}</strong>{" "}
          {d.nao_revisadas === 1
            ? "transação aguardando"
            : "transações aguardando"}{" "}
          revisão
        </span>
        <span className="inline-flex items-center gap-1 font-medium text-accent-ink">
          Revisar
          <ArrowRight
            className="size-4 transition-transform duration-200 ease-(--ease-out) group-hover:translate-x-0.5 motion-reduce:transition-none"
            aria-hidden
          />
        </span>
      </Link>
    ) : null

  const widgets: Record<string, () => ReactNode> = {
    "kpi-saldo": () =>
      dashMes.isError ? (
        <ErroCard />
      ) : !d ? (
        <Skeleton className="h-full min-h-36 w-full rounded-xl" />
      ) : (
        <SaldoDestaque
          centavos={d.saldo_total_centavos}
          contas={contas.data?.filter((c) => c.type === "BANK").length}
          pontos={saldoSerie}
          oculto={oculto}
        />
      ),
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
    ultimas: () => (
      <CardGrafico
        titulo="Últimas transações"
        descricao="As 10 mais recentes"
        acao={
          <Button asChild variant="ghost" size="sm">
            <Link to="/transacoes">Ver todas</Link>
          </Button>
        }
      >
        <div className="space-y-3">
          {pendentes}
          {ultimas.isLoading ? (
            <Skeleton className="h-[420px] w-full" />
          ) : ultimas.isError ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              Não foi possível carregar as transações.
            </p>
          ) : ultimas.data?.items.length ? (
            <TransacoesTabela items={ultimas.data.items} semMoldura />
          ) : (
            <p className="py-8 text-center text-sm text-muted-foreground">
              Nenhuma transação ainda.
            </p>
          )}
        </div>
      </CardGrafico>
    ),
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
        ) : serieFluxo.isError ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            Não foi possível carregar entradas e saídas.
          </p>
        ) : (
          <GraficoFluxo
            buckets={serieFluxo.data?.buckets ?? []}
            granularidade={granFluxo}
          />
        )}
      </CardGrafico>
    ),
    calendario: () => <CalendarioCalor fim={fim} visao={visao} />,
    "despesas-fixas": () => <DespesasFixasMesWidget />,
    "despesas-fixas-proximos": () => <DespesasFixasProximosWidget />,
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
  }

  return (
    <Tabs value={aba} onValueChange={trocarAba} className="gap-4">
      <PageHeader
        titulo="Dashboard"
        descricao="Análise do período: fluxo, categorias, calendário e patrimônio — personalizável."
      />
      {/* Abas no topo; o período, a visão e o personalizar abaixo valem para a aba aberta. */}
      <TabsList variant="line" className="w-full justify-start border-b">
        <TabsTrigger value="geral" disabled={editando}>
          Geral
        </TabsTrigger>
        <TabsTrigger value="receitas" disabled={editando}>
          Receitas
        </TabsTrigger>
        <TabsTrigger value="despesas" disabled={editando}>
          Despesas
        </TabsTrigger>
      </TabsList>
      <div className="flex flex-wrap items-center justify-between gap-2">
        {/* Mobile: o período mora num botão "Filtros" (gaveta), não espalhado pelo topo. */}
        <FiltrosMobile inicio={inicio} fim={fim} onChange={mudarPeriodo} />
        <div className="hidden flex-wrap items-center gap-2 md:flex">
          <FiltrosRapidos inicio={inicio} fim={fim} onChange={mudarPeriodo} />
          <PeriodoPicker inicio={inicio} fim={fim} onChange={mudarPeriodo} />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {editando ? (
            <>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={ocultos.length === 0 || salvar.isPending}
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
                      onSelect={() => alterar(w.id, { visivel: true })}
                    >
                      {TITULO.get(w.id)}
                    </DropdownMenuItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
              <Button
                variant="ghost"
                size="sm"
                disabled={salvar.isPending}
                onClick={() =>
                  setRascunho((r) => restaurarAba(r ?? salvo, aba))
                }
              >
                <RotateCcw aria-hidden />
                Restaurar padrão
              </Button>
              <Button
                variant="ghost"
                size="sm"
                disabled={salvar.isPending}
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
              <ToggleGroup
                type="single"
                size="sm"
                variant="outline"
                spacing={0}
                value={visao}
                onValueChange={(v) => v && trocarVisao(v as Visao)}
                aria-label="Visão dos valores"
              >
                <ToggleGroupItem
                  value="competencia"
                  title="Compras no cartão na data da compra; pagamento de fatura fica de fora"
                >
                  Competência
                </ToggleGroupItem>
                <ToggleGroupItem
                  value="caixa"
                  title="Só o que saiu da conta: pagamento de fatura no lugar das compras no cartão"
                >
                  Caixa
                </ToggleGroupItem>
              </ToggleGroup>
              <Button
                variant="outline"
                size="icon-sm"
                onClick={alternarOculto}
                aria-pressed={oculto}
                aria-label="Ocultar valores"
                title={oculto ? "Valores ocultos" : "Ocultar valores"}
              >
                {oculto ? <EyeOff aria-hidden /> : <Eye aria-hidden />}
              </Button>
              <SyncButton compacto />
              <Button
                variant="outline"
                size="sm"
                // Antes do perfil chegar, "salvo" é o padrão: editar dali sobrescreveria o layout.
                disabled={!perfil.data}
                onClick={() => setRascunho(salvo)}
              >
                <LayoutGrid aria-hidden />
                <span className="max-sm:sr-only">Personalizar</span>
              </Button>
            </>
          )}
        </div>
      </div>

      {editando ? (
        <p className="rounded-lg bg-muted/60 px-4 py-2.5 text-sm text-muted-foreground">
          Arraste os blocos para reordenar (no celular, toque e segure). Em
          telas largas, puxe a borda direita ou a de baixo para mudar largura e
          altura — duplo clique na borda de baixo volta à altura automática. Os
          ocultos voltam por “Adicionar visualização”.
        </p>
      ) : null}
      <TabsContent value="geral" className="space-y-4">
        {/* Pendentes moram acima da tabela de últimas transações; sem ela visível, ficam no topo. */}
        {visiveis.some((w) => w.id === "ultimas") ? null : pendentes}

        {grade(widgets)}
      </TabsContent>
      <TabsContent value="receitas">
        <AbaReceitas
          grade={grade}
          periodo={periodo}
          rotuloPeriodo={rotuloPeriodo}
          rotulo={rotulo}
          oculto={oculto}
          visao={visao}
        />
      </TabsContent>
      <TabsContent value="despesas">
        <AbaDespesas
          grade={grade}
          periodo={periodo}
          rotuloPeriodo={rotuloPeriodo}
          rotulo={rotulo}
          oculto={oculto}
          visao={visao}
        />
      </TabsContent>
    </Tabs>
  )
}

/** Mobile (`< md`): botão com o período atual que abre os filtros numa gaveta inferior. */
function FiltrosMobile({
  inicio,
  fim,
  onChange,
}: {
  inicio: string
  fim: string
  onChange: (inicio: string, fim: string) => void
}) {
  const resumo = `${formatBucketLabel(inicio, "diaria")} – ${formatBucketLabel(fim, "diaria")}`
  return (
    <Drawer>
      <DrawerTrigger asChild>
        <Button variant="outline" size="sm" className="md:hidden">
          <SlidersHorizontal aria-hidden />
          Filtros
          <span className="text-muted-foreground tabular-nums">{resumo}</span>
        </Button>
      </DrawerTrigger>
      <DrawerContent className="md:hidden">
        <DrawerHeader className="group-data-[vaul-drawer-direction=bottom]/drawer-content:text-left">
          <DrawerTitle>Filtros</DrawerTitle>
          <DrawerDescription>
            Período dos gráficos. Os cards “no mês” seguem o mês corrente.
          </DrawerDescription>
        </DrawerHeader>
        <div className="space-y-3 px-4">
          <p className="text-sm font-medium">Período</p>
          <FiltrosRapidos inicio={inicio} fim={fim} onChange={onChange} />
          <PeriodoPicker inicio={inicio} fim={fim} onChange={onChange} />
        </div>
        <DrawerFooter className="pb-[calc(1rem+env(safe-area-inset-bottom))]">
          <DrawerClose asChild>
            <Button>Pronto</Button>
          </DrawerClose>
        </DrawerFooter>
      </DrawerContent>
    </Drawer>
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
