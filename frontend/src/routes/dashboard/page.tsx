import { AlertTriangle, ArrowRight, Landmark, PiggyBank } from "lucide-react"
import { useMemo, useState } from "react"
import { Link } from "react-router"

import {
  BarrasEmpilhadasCategorias,
  DistribuicaoCategorias,
  GraficoFluxo,
  RoscaEntradasSaidas,
} from "@/components/dashboard/graficos"
import { KpiCard } from "@/components/dashboard/kpi-card"
import { PeriodoPicker } from "@/components/dashboard/periodo-picker"
import { EmptyState } from "@/components/common/empty-state"
import { Valor } from "@/components/common/valor"
import { SyncButton } from "@/components/sync-button"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { useCategorias, nomeCategoria } from "@/lib/api/categorias"
import { useContas } from "@/lib/api/contas"
import {
  useDashboard,
  useDashboardSeries,
  type Granularidade,
} from "@/lib/api/dashboard"
import {
  addDias,
  formatDate,
  hojeISO,
  mesAteHoje,
  mesmoPeriodoMesAnterior,
  subMeses,
  ultimos6MesesCompletos,
} from "@/lib/format"

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

/** Variação relativa vs. período anterior; `null` quando não há base de comparação. */
function variacao(atual: number, anterior: number | undefined): number | null {
  if (anterior == null || anterior === 0) return null
  return (atual - anterior) / Math.abs(anterior)
}

export function DashboardPage() {
  // Cards do topo: sempre mês corrente até hoje, comparados ao mesmo período do mês anterior.
  const mes = mesAteHoje()
  const dashMes = useDashboard(mes)
  const dashMesAnterior = useDashboard(
    mesmoPeriodoMesAnterior(mes.inicio, mes.fim)
  )
  // Tendência dos cards: mesma métrica nos últimos 6 meses completos (uma query, os 3 cards a compartilham).
  const tendencia = useDashboardSeries(ultimos6MesesCompletos(), "mensal")
  const buckets6m = tendencia.data?.buckets ?? []

  // Seletor de período: manda apenas na análise abaixo, não nos cards do topo.
  const [inicio, setInicio] = useState(mes.inicio)
  const [fim, setFim] = useState(mes.fim)
  const periodo = { inicio, fim }

  const [granFluxo, setGranFluxo] = useState<Granularidade>("semanal")
  const serieFluxo = useDashboardSeries(periodo, granFluxo)
  const [granCat, setGranCat] = useState<Granularidade>("semanal")
  const serieCat = useDashboardSeries(periodo, granCat)
  const dashPeriodo = useDashboard(periodo) // rosca "Período consolidado" segue o seletor

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

  return (
    <div className="space-y-8">
      <section className="space-y-3">
        <div className="flex items-end justify-between gap-3">
          <div>
            <h2 className="text-sm font-medium">Este mês até hoje</h2>
            <p className="text-xs text-muted-foreground">
              Comparado ao mesmo período do mês anterior
            </p>
          </div>
          <SyncButton />
        </div>

        {dashMes.isError ? (
          <EmptyState
            icon={AlertTriangle}
            title="Não foi possível carregar o painel"
            description="Tente novamente em instantes."
          />
        ) : dashMes.isLoading || !dashMes.data ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {[0, 1, 2, 3, 4].map((i) => (
              <Skeleton key={i} className="h-28 w-full" />
            ))}
          </div>
        ) : (
          <>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
              <KpiCard
                label="Saldo em contas"
                centavos={dashMes.data.saldo_total_centavos}
              />
              <KpiCard
                label="Entradas no mês"
                centavos={dashMes.data.entradas_centavos}
                sinal
                delta={variacao(
                  dashMes.data.entradas_centavos,
                  ant?.entradas_centavos
                )}
                serie={buckets6m}
                campo="entradas_centavos"
              />
              <KpiCard
                label="Saídas no mês"
                centavos={-dashMes.data.saidas_centavos}
                delta={variacao(
                  dashMes.data.saidas_centavos,
                  ant?.saidas_centavos
                )}
                serie={buckets6m}
                campo="saidas_centavos"
              />
              <KpiCard
                label="Resultado no mês"
                centavos={dashMes.data.resultado_centavos}
                sinal
                delta={variacao(
                  dashMes.data.resultado_centavos,
                  ant?.resultado_centavos
                )}
                serie={buckets6m}
                campo="resultado_centavos"
              />
              <KpiCard
                label="Investido no mês"
                centavos={dashMes.data.investido_centavos}
                sinal
                delta={variacao(
                  dashMes.data.investido_centavos,
                  ant?.investido_centavos
                )}
                serie={buckets6m}
                campo="investido_centavos"
              />
            </div>

            {dashMes.data.nao_revisadas > 0 ? (
              <Link
                to="/transacoes?pendente=true"
                className="flex items-center justify-between rounded-lg border border-dashed bg-muted/40 px-4 py-3 text-sm transition-colors hover:bg-muted"
              >
                <span>
                  <strong>{dashMes.data.nao_revisadas}</strong> transação(ões)
                  aguardando revisão
                </span>
                <ArrowRight
                  className="size-4 text-muted-foreground"
                  aria-hidden
                />
              </Link>
            ) : null}
          </>
        )}
      </section>

      <section className="space-y-4">
        <div className="flex flex-wrap items-end justify-between gap-2">
          <div>
            <h2 className="text-sm font-medium">Análise do período</h2>
            <p className="text-xs text-muted-foreground">
              Definida pelo seletor de período, independente dos cards acima
            </p>
          </div>
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
        </div>

        <Card>
          <CardHeader className="flex-row items-start justify-between gap-4">
            <div>
              <CardTitle className="text-base">Entradas e saídas</CardTitle>
              <CardDescription>
                Fluxo por {PERIODO_LABEL[granFluxo]} no período
              </CardDescription>
            </div>
            <SeletorGranularidade valor={granFluxo} onChange={setGranFluxo} />
          </CardHeader>
          <CardContent>
            {serieFluxo.isLoading ? (
              <Skeleton className="h-[280px] w-full" />
            ) : (
              <GraficoFluxo
                buckets={serieFluxo.data?.buckets ?? []}
                granularidade={granFluxo}
              />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex-row items-start justify-between gap-4">
            <div>
              <CardTitle className="text-base">
                Despesas por categoria
              </CardTitle>
              <CardDescription>
                Todas as despesas do período (exclui transferências e
                investimentos)
              </CardDescription>
            </div>
            <SeletorGranularidade valor={granCat} onChange={setGranCat} />
          </CardHeader>
          <CardContent className="space-y-8">
            {/* Distribuição: total do período inteiro (não depende da granularidade). */}
            {dashPeriodo.isLoading ? (
              <Skeleton className="h-[260px] w-full" />
            ) : (
              <DistribuicaoCategorias
                gastos={dashPeriodo.data?.gasto_por_categoria ?? []}
                rotulo={rotulo}
              />
            )}
            <SecaoGrafico
              titulo={`Por ${PERIODO_LABEL[granCat]}`}
              carregando={serieCat.isLoading}
            >
              <BarrasEmpilhadasCategorias
                buckets={serieCat.data?.buckets ?? []}
                granularidade={granCat}
                rotulo={rotulo}
                comLegenda={false}
              />
            </SecaoGrafico>
          </CardContent>
        </Card>

        <Card className="lg:max-w-md">
          <CardHeader>
            <CardTitle className="text-base">Período consolidado</CardTitle>
            <CardDescription>Distribuição de entradas e saídas</CardDescription>
          </CardHeader>
          <CardContent>
            {dashPeriodo.isLoading ? (
              <Skeleton className="h-[240px] w-full" />
            ) : (
              <RoscaEntradasSaidas
                entradas={dashPeriodo.data?.entradas_centavos ?? 0}
                saidas={dashPeriodo.data?.saidas_centavos ?? 0}
              />
            )}
          </CardContent>
        </Card>

        {dashMes.data && dashMes.data.faturas_abertas.length > 0 ? (
          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle className="text-base">
                <PiggyBank className="mr-2 inline size-4" aria-hidden />
                Faturas em aberto
              </CardTitle>
              <Button asChild variant="ghost" size="sm">
                <Link to="/faturas">Ver faturas</Link>
              </Button>
            </CardHeader>
            <CardContent className="space-y-1">
              {dashMes.data.faturas_abertas.map((f) => (
                <Link
                  key={f.id}
                  to={`/faturas/${f.id}`}
                  className="flex items-center justify-between py-1.5 text-sm transition-colors hover:text-primary"
                >
                  <span>Vencimento {formatDate(f.due_date)}</span>
                  <Valor centavos={-f.total_amount_centavos} />
                </Link>
              ))}
            </CardContent>
          </Card>
        ) : null}
      </section>
    </div>
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

function SecaoGrafico({
  titulo,
  carregando,
  children,
}: {
  titulo: string
  carregando: boolean
  children: React.ReactNode
}) {
  return (
    <div className="space-y-2">
      <p className="text-sm text-muted-foreground">{titulo}</p>
      {carregando ? <Skeleton className="h-[240px] w-full" /> : children}
    </div>
  )
}
