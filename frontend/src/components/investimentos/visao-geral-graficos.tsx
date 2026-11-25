import { ArrowRight, CalendarClock } from "lucide-react"
import { useState } from "react"
import { Link } from "react-router"

import {
  GraficoBarras,
  GraficoBarrasAgrupadas,
} from "@/components/common/graficos-base"
import { Valor } from "@/components/common/valor"
import { eixoBRL } from "@/components/dashboard/chart-helpers"
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
import { useIndicadoresSerie } from "@/lib/api/indicadores"
import {
  useCarteiraSerie,
  type CarteiraItem,
  type RecorteCarteira,
  type VisaoGeralInvestimentos,
} from "@/lib/api/investimentos"
import { corTexto, intensidade, misturar } from "@/lib/calendario-calor"
import { useTemaGrafico } from "@/lib/echart-tema"
import {
  formatBRL,
  formatBucketLabel,
  formatDataISO,
  formatMesAno,
  formatPct,
  hojeISO,
  subMeses,
} from "@/lib/format"
import {
  aPartirDaPrimeiraPosicao,
  fechamentosMensais,
  matrizRentabilidade,
  vencimentosPorMes,
} from "@/lib/investimentos-visao"
import { retornoMensal } from "@/lib/tesouro"
import { cn } from "@/lib/utils"

// Gráficos da Visão Geral de investimentos. Rentabilidade mês a mês e Aportes × valorização leem a
// MESMA série de 5 anos (mesma chave de query → uma requisição só).

const MESES_SERIE = 60
const mesCurto = (mes: string) => formatBucketLabel(`${mes}-01`, "mensal")
const mascarar = () => "R$ ••••"
const mascararEixo = () => "••••"

function useSerieLonga(recorte: RecorteCarteira = "todos") {
  const fim = hojeISO()
  return useCarteiraSerie({
    recorte,
    inicio: subMeses(fim, MESES_SERIE),
    fim,
  })
}

function Carregando({ altura = "h-56" }: { altura?: string }) {
  return <Skeleton className={cn("w-full", altura)} />
}

function SemDados({ children }: { children: React.ReactNode }) {
  return (
    <p className="py-10 text-center text-sm text-muted-foreground">
      {children}
    </p>
  )
}

// --- proventos por mês -------------------------------------------------------------------------

export function ProventosPorMes({
  vg,
  carregando,
  erro,
  oculto,
}: {
  vg: VisaoGeralInvestimentos | undefined
  carregando: boolean
  erro: boolean
  oculto: boolean
}) {
  const meses = vg?.proventos_mensais ?? []
  const total = meses.reduce((s, m) => s + m.centavos, 0)
  return (
    <Card className="h-full min-w-0">
      <CardHeader>
        <CardTitle className="text-base">Proventos por mês</CardTitle>
        <CardDescription>
          Dividendos e rendimentos recebidos nos últimos 12 meses
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {carregando ? (
          <Carregando />
        ) : erro || !vg ? (
          <SemDados>Não foi possível carregar os proventos.</SemDados>
        ) : total === 0 ? (
          <SemDados>Nenhum provento recebido nos últimos 12 meses.</SemDados>
        ) : (
          <>
            <dl className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <dt className="text-muted-foreground">Total em 12 meses</dt>
                <dd className="text-lg font-bold">
                  <Valor centavos={total} neutro oculto={oculto} />
                </dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Média mensal</dt>
                <dd className="text-lg font-bold">
                  <Valor
                    centavos={Math.round(total / meses.length)}
                    neutro
                    oculto={oculto}
                  />
                </dd>
              </div>
            </dl>
            <GraficoBarras
              dados={meses}
              x="mes"
              chave="centavos"
              nome="Proventos"
              cor="var(--positive)"
              formatarX={mesCurto}
              formatarRotulo={(m) => formatMesAno(`${m}-15`)}
              formatarY={oculto ? mascararEixo : eixoBRL}
              formatarValor={oculto ? mascarar : formatBRL}
              altura={220}
              ariaLabel="Proventos recebidos por mês nos últimos 12 meses"
            />
          </>
        )}
      </CardContent>
    </Card>
  )
}

// --- aportes × valorização ---------------------------------------------------------------------

export function AportesValorizacao({ oculto }: { oculto: boolean }) {
  const serie = useSerieLonga()
  // Últimos 24 meses (o corrente vale até hoje: é dele que saem os números do topo) com custo
  // conhecido: aportado embaixo, rendimento (pode ser < 0) em cima.
  const mesAtual = hojeISO().slice(0, 7)
  const custoCompleto = serie.data?.investido_completo ?? true
  const meses = fechamentosMensais(serie.data?.pontos ?? [])
    .filter((m) => m.investido != null)
    .slice(-24)
    .map((m) => ({
      mes: m.mes,
      aportado: m.investido!,
      rendimento: m.valor - m.investido!,
    }))
  const ultimo = meses.at(-1)
  return (
    <Card className="h-full min-w-0">
      <CardHeader>
        <CardTitle className="text-base">Aportes × valorização</CardTitle>
        <CardDescription>
          Quanto do patrimônio é dinheiro aportado e quanto é rendimento
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {serie.isLoading ? (
          <Carregando />
        ) : serie.isError ? (
          <SemDados>Não foi possível carregar a evolução da carteira.</SemDados>
        ) : !custoCompleto ? (
          <SemDados>
            Parte da carteira não informa o custo de compra, então não dá para
            separar aporte de rendimento sem inflar o rendimento. Complete os
            aportes das posições na Carteira.
          </SemDados>
        ) : !ultimo ? (
          <SemDados>
            Ainda sem histórico de aportes para comparar. O gráfico aparece
            depois dos primeiros fechamentos mensais.
          </SemDados>
        ) : (
          <>
            <dl className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <dt className="text-muted-foreground">Aportado</dt>
                <dd className="text-lg font-bold">
                  <Valor centavos={ultimo.aportado} neutro oculto={oculto} />
                </dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Rendimento</dt>
                <dd className="text-lg font-bold">
                  <Valor centavos={ultimo.rendimento} sinal oculto={oculto} />
                </dd>
              </div>
            </dl>
            <GraficoBarrasAgrupadas
              empilhada
              // Mês com perda: o trecho negativo é desenhado do topo do aportado para baixo (por
              // cima dele), na cor de perda — o cinza visível que sobra é o patrimônio.
              destaque={{
                serie: 1,
                cor: "var(--negative)",
                quando: (i) => meses[i]!.rendimento < 0,
              }}
              dados={meses}
              x="mes"
              series={[
                {
                  chave: "aportado",
                  nome: "Aportado",
                  cor: "var(--muted-foreground)",
                },
                {
                  chave: "rendimento",
                  nome: "Rendimento",
                  cor: "var(--positive)",
                },
              ]}
              formatarX={mesCurto}
              formatarRotulo={(m) =>
                formatMesAno(`${m}-15`) + (m === mesAtual ? " (até hoje)" : "")
              }
              formatarY={oculto ? mascararEixo : eixoBRL}
              formatarValor={oculto ? mascarar : formatBRL}
              altura={240}
              ariaLabel="Patrimônio no fim de cada mês dividido em valor aportado e rendimento"
            />
          </>
        )}
      </CardContent>
    </Card>
  )
}

// --- rentabilidade mês a mês -------------------------------------------------------------------

const NOMES_MES = [
  "Jan",
  "Fev",
  "Mar",
  "Abr",
  "Mai",
  "Jun",
  "Jul",
  "Ago",
  "Set",
  "Out",
  "Nov",
  "Dez",
]

/** O que arredonda para zero em 1 casa É zero: texto "0,0%" (não "−0,0%") e célula sem cor. */
const arred = (v: number) => (Math.abs(v) < 0.05 ? 0 : v)
const pct1 = (v: number) => formatPct(arred(v), { casas: 1 })

const RECORTES: { valor: RecorteCarteira; rotulo: string }[] = [
  { valor: "todos", rotulo: "Todos" },
  { valor: "renda_fixa", rotulo: "Renda fixa" },
  { valor: "renda_variavel", rotulo: "Renda variável" },
]

/** Mapa de calor ano × mês do retorno (TWR) da carteira, azul positivo → laranja negativo, com o
 *  acumulado do ano e o CDI do mesmo período, filtrável por classe (todos/renda fixa/variável).
 *  Percentual não é valor: não mascara no modo privacidade. */
export function RentabilidadeMensal() {
  const tema = useTemaGrafico()
  // "Todos" reaproveita a série do Aportes × valorização (mesma chave de query).
  const [recorte, setRecorte] = useState<RecorteCarteira>("todos")
  const serie = useSerieLonga(recorte)
  const pontos = aPartirDaPrimeiraPosicao(serie.data?.pontos ?? [])
  const inicio = pontos[0]?.data ?? hojeISO()
  const cdi = useIndicadoresSerie(pontos.length >= 2 ? ["cdi"] : [], {
    inicio,
    fim: hojeISO(),
  })
  const linhas = matrizRentabilidade(
    retornoMensal(pontos),
    retornoMensal(cdi.data?.find((s) => s.codigo === "cdi")?.pontos ?? [])
  )
  const valores = linhas.flatMap((l) =>
    l.meses.filter((v): v is number => v != null)
  )
  const maxPos = Math.max(0, ...valores)
  const maxNeg = Math.max(0, ...valores.map((v) => -v))

  const estilo = (v: number) => {
    const i = intensidade(v, maxPos, maxNeg)
    const fundo =
      i === 0
        ? tema.superficie
        : misturar(
            tema.superficie,
            i > 0 ? tema.positivo : tema.negativo,
            Math.abs(i)
          )
    return {
      background: fundo,
      color: corTexto(fundo, [
        tema.texto,
        tema.superficie,
        "rgb(0,0,0)",
        "rgb(255,255,255)",
      ]),
    }
  }

  return (
    <Card className="h-full min-w-0">
      <CardHeader className="flex-row flex-wrap items-start justify-between gap-x-4 gap-y-3">
        <div className="min-w-0 space-y-1.5">
          <CardTitle className="text-base">Rentabilidade mês a mês</CardTitle>
          <CardDescription>
            Retorno em cada mês completo, com o acumulado do ano e o CDI no
            mesmo período
          </CardDescription>
        </div>
        <ToggleGroup
          type="single"
          size="sm"
          variant="outline"
          spacing={0}
          value={recorte}
          onValueChange={(v) => v && setRecorte(v as RecorteCarteira)}
          aria-label="Classe de ativos"
        >
          {RECORTES.map((r) => (
            <ToggleGroupItem key={r.valor} value={r.valor}>
              {r.rotulo}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      </CardHeader>
      <CardContent>
        {serie.isLoading ? (
          <Carregando altura="h-40" />
        ) : serie.isError ? (
          <SemDados>Não foi possível carregar a rentabilidade.</SemDados>
        ) : linhas.length === 0 ? (
          <SemDados>
            {recorte === "todos"
              ? "Precisa de pelo menos um mês completo de histórico da carteira."
              : `Sem ${recorte === "renda_fixa" ? "renda fixa" : "renda variável"} com um mês completo de histórico.`}
          </SemDados>
        ) : (
          // Tabela larga: rola sozinha no celular (a página nunca rola na horizontal).
          <div className="-mx-2 overflow-x-auto px-2">
            <table className="w-full min-w-[40rem] border-separate border-spacing-0.5 text-xs tabular-nums">
              <caption className="sr-only">
                Rentabilidade mensal da carteira por ano, com o acumulado do ano
                e o CDI do mesmo período
              </caption>
              <thead>
                <tr className="text-muted-foreground">
                  <th scope="col" className="text-left font-medium">
                    Ano
                  </th>
                  {NOMES_MES.map((m) => (
                    <th key={m} scope="col" className="font-medium">
                      {m}
                    </th>
                  ))}
                  <th scope="col" className="font-medium">
                    No ano
                  </th>
                  <th scope="col" className="font-medium">
                    CDI
                  </th>
                </tr>
              </thead>
              <tbody>
                {linhas.map((l) => (
                  <tr key={l.ano}>
                    <th scope="row" className="pr-1 text-left font-medium">
                      {l.ano}
                    </th>
                    {l.meses.map((v, i) => (
                      <td
                        key={i}
                        className={cn(
                          "h-8 rounded-md px-1 text-center",
                          v == null && "text-muted-foreground"
                        )}
                        style={v != null ? estilo(arred(v)) : undefined}
                        title={
                          v != null
                            ? `${NOMES_MES[i]}/${l.ano}: ${formatPct(v)}` +
                              (l.cdi[i] != null
                                ? ` · CDI ${formatPct(l.cdi[i]!)}`
                                : "")
                            : undefined
                        }
                      >
                        {v != null ? pct1(v) : "—"}
                      </td>
                    ))}
                    <td
                      className={cn(
                        "rounded-md bg-muted px-1.5 text-center font-semibold",
                        l.total != null && l.total < 0
                          ? "text-negative-ink"
                          : "text-foreground"
                      )}
                    >
                      {l.total != null ? formatPct(l.total, { casas: 1 }) : "—"}
                    </td>
                    <td className="px-1 text-center text-muted-foreground">
                      {l.totalCdi != null
                        ? formatPct(l.totalCdi, { casas: 1 })
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

// --- vencimentos de renda fixa -----------------------------------------------------------------

const MAX_MESES_VENC = 6

export function VencimentosRendaFixa({
  itens,
  carregando,
  oculto,
}: {
  itens: CarteiraItem[]
  carregando: boolean
  oculto: boolean
}) {
  const grupos = vencimentosPorMes(itens, hojeISO())
  const visiveis = grupos.slice(0, MAX_MESES_VENC)
  const maior = Math.max(1, ...visiveis.map((g) => g.total))
  return (
    <Card className="h-full min-w-0">
      <CardHeader>
        <CardTitle className="text-base">Vencimentos da renda fixa</CardTitle>
        <CardDescription>
          O que vence nos próximos meses, para planejar o reinvestimento
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {carregando ? (
          <Carregando altura="h-40" />
        ) : grupos.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-8 text-center">
            <CalendarClock
              className="size-6 text-muted-foreground"
              aria-hidden
            />
            <p className="text-sm text-muted-foreground">
              Nenhum título com vencimento pela frente.
            </p>
          </div>
        ) : (
          <>
            <ol className="space-y-3">
              {visiveis.map((g) => (
                <li key={g.mes} className="space-y-1.5">
                  <div className="flex items-baseline justify-between gap-3 text-sm">
                    <span className="font-medium first-letter:uppercase">
                      {formatMesAno(`${g.mes}-15`)}
                    </span>
                    <Valor
                      centavos={g.total}
                      neutro
                      oculto={oculto}
                      className="font-semibold"
                    />
                  </div>
                  <div
                    className="h-1.5 overflow-hidden rounded-full bg-muted"
                    aria-hidden
                  >
                    <div
                      className="h-full rounded-full bg-primary"
                      style={{ width: `${(g.total / maior) * 100}%` }}
                    />
                  </div>
                  <p className="truncate text-xs text-muted-foreground">
                    {g.itens
                      .slice(0, 2)
                      .map(
                        (i) =>
                          `${i.nome ?? "Título"} (${formatDataISO(i.due_date!.slice(0, 10))})`
                      )
                      .join(" · ")}
                    {g.itens.length > 2 ? ` · +${g.itens.length - 2}` : ""}
                  </p>
                </li>
              ))}
            </ol>
            {grupos.length > MAX_MESES_VENC ? (
              <p className="text-xs text-muted-foreground">
                E mais {grupos.length - MAX_MESES_VENC}{" "}
                {grupos.length - MAX_MESES_VENC === 1 ? "mês" : "meses"} com
                vencimentos.
              </p>
            ) : null}
            <Button asChild variant="ghost" size="sm" className="w-full">
              <Link to="/investimentos/carteira">
                Ver na carteira
                <ArrowRight className="size-4" aria-hidden />
              </Link>
            </Button>
          </>
        )}
      </CardContent>
    </Card>
  )
}
