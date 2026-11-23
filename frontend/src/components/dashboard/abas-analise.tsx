import { ArrowRight } from "lucide-react"
import { useCallback, useMemo, useState, type ReactNode } from "react"
import { Link } from "react-router"

import {
  GraficoBarras,
  GraficoBarrasAgrupadas,
  GraficoLinhas,
  type SerieLinha,
} from "@/components/common/graficos-base"
import {
  CardGrafico,
  ErroCard,
  Estado,
  SeletorGranularidade,
} from "@/components/dashboard/card-grafico"
import { eixoBRL } from "@/components/dashboard/chart-helpers"
import {
  BarrasEmpilhadasCategorias,
  DistribuicaoCategorias,
  type CategoriaSelecionada,
} from "@/components/dashboard/graficos"
import { KpiCard } from "@/components/dashboard/kpi-card"
import { PainelCartoes } from "@/components/dashboard/painel-cartoes"
import {
  TransacoesAnaliseDialog,
  TransacoesOrcamentoDialog,
} from "@/components/dashboard/transacoes-dialog"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import {
  useAnalise,
  useDashboard,
  useDashboardSeries,
  type AnaliseNatureza,
  type FiltroAnalise,
  PERIODO_LABEL,
  type Granularidade,
  type Natureza,
} from "@/lib/api/dashboard"
import { useConsumoOrcamentos, type AlvoDrilldown } from "@/lib/api/orcamentos"
import {
  addDias,
  formatBRL,
  formatBucketLabel,
  mesAteHoje,
  ultimos6MesesCompletos,
} from "@/lib/format"

type Periodo = { inicio: string; fim: string }

const DIAS = [
  "Segunda",
  "Terça",
  "Quarta",
  "Quinta",
  "Sexta",
  "Sábado",
  "Domingo",
]
const DIAS_CURTOS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]

const diaMes = (iso: string) => formatBucketLabel(iso, "diaria")
const mesAno = (yyyyMm: string) => formatBucketLabel(`${yyyyMm}-01`, "mensal")
const pct = (v: number) => `${Math.round(v * 100)}%`
const curto = (s: string) => (s.length > 14 ? `${s.slice(0, 13)}…` : s)

function variacao(atual: number, anterior: number): number | null {
  return anterior === 0 ? null : (atual - anterior) / Math.abs(anterior)
}

/** Linha de tooltip sem marcador (HTML do ECharts; textos fixos, sem dado do usuário). */
const nota = (texto: string, forte = false) =>
  `<div style="${forte ? "font-weight:500" : "opacity:.75"}">${texto}</div>`

const NOMES = {
  receita: { plural: "Receitas", acao: "Recebido", contraparte: "fontes" },
  despesa: {
    plural: "Despesas",
    acao: "Gasto",
    contraparte: "estabelecimentos",
  },
} as const

// --- KPIs --------------------------------------------------------------------------------------

function Kpis({
  natureza,
  analise,
  oculto,
}: {
  natureza: Natureza
  analise: ReturnType<typeof useAnalise>
  oculto: boolean
}) {
  // Tendência de 6 meses: mesma query compartilhada com os cards da aba Geral.
  const tendencia = useDashboardSeries(ultimos6MesesCompletos(), "mensal")
  const a = analise.data
  const grade = "grid grid-cols-2 gap-3 sm:gap-4 @3xl:grid-cols-4"
  if (analise.isError)
    return (
      <div className={grade}>
        <ErroCard />
      </div>
    )
  if (!a)
    return (
      <div className={grade}>
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-28 w-full rounded-xl" />
        ))}
      </div>
    )
  const n = NOMES[natureza]
  const anterior = `${diaMes(a.anterior_inicio)} a ${diaMes(a.anterior_fim)}`
  const meses = a.previsto.filter((p) => p.previsto_centavos != null)
  const orcado = meses.reduce((s, p) => s + (p.previsto_centavos ?? 0), 0)
  const realizadoOrcado = meses.reduce((s, p) => s + p.realizado_centavos, 0)
  const dias = a.dias_semana.reduce((s, d) => s + d.ocorrencias, 0)
  return (
    <div className={grade}>
      <KpiCard
        label={`${n.acao} no período`}
        centavos={a.total_centavos}
        delta={variacao(a.total_centavos, a.anterior_centavos)}
        tituloDelta={`Comparado a ${anterior}`}
        serie={tendencia.data?.buckets}
        campo={natureza === "receita" ? "entradas_centavos" : "saidas_centavos"}
        oculto={oculto}
      />
      <KpiCard
        label="Período anterior"
        centavos={a.anterior_centavos}
        rodape={anterior}
        oculto={oculto}
      />
      {natureza === "receita" ? (
        <KpiCard
          label="Média por recebimento"
          centavos={
            a.quantidade ? Math.round(a.total_centavos / a.quantidade) : 0
          }
          rodape={`${a.quantidade} ${a.quantidade === 1 ? "recebimento" : "recebimentos"}`}
          oculto={oculto}
        />
      ) : (
        <KpiCard
          label="Média diária"
          centavos={dias ? Math.round(a.total_centavos / dias) : 0}
          rodape={`em ${dias} ${dias === 1 ? "dia" : "dias"}`}
          oculto={oculto}
        />
      )}
      <KpiCard
        label={natureza === "receita" ? "Previsto (orçamento)" : "Orçamento"}
        centavos={orcado}
        rodape={
          meses.length === 0
            ? `Sem orçamento de ${natureza} no período`
            : `${natureza === "receita" ? "Recebido" : "Gasto"}: ${pct(orcado ? realizadoOrcado / orcado : 0)} do ${natureza === "receita" ? "previsto" : "orçado"}`
        }
        oculto={oculto}
      />
    </div>
  )
}

// --- Maiores fontes / estabelecimentos (barras horizontais) -------------------------------------

function RankingContrapartes({
  a,
  natureza,
  onSelecionar,
}: {
  a: AnaliseNatureza
  natureza: Natureza
  onSelecionar: (f: FiltroAnalise) => void
}) {
  if (a.contrapartes.length === 0) return <SemDados />
  const max = a.contrapartes[0].total_centavos
  const linha = (nome: string, valor: number) => (
    <>
      <div className="flex items-baseline justify-between gap-3 text-sm">
        <span className="truncate">{nome}</span>
        <span className="shrink-0 tabular-nums">
          {formatBRL(valor)}
          <span className="ml-1.5 text-xs text-muted-foreground">
            {a.total_centavos ? pct(valor / a.total_centavos) : "—"}
          </span>
        </span>
      </div>
      <div className="mt-1.5 h-2 rounded-full bg-muted" aria-hidden>
        <div
          className="h-full rounded-full bg-primary"
          style={{ width: `${Math.max((valor / max) * 100, 1)}%` }}
        />
      </div>
    </>
  )
  return (
    <ul
      className="space-y-1"
      aria-label={`Maiores ${NOMES[natureza].contraparte}`}
    >
      {a.contrapartes.map((c) => (
        <li key={c.chave}>
          <button
            type="button"
            className="block w-full cursor-pointer rounded-md px-2 py-2 text-left hover:bg-muted/60 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
            onClick={() =>
              onSelecionar({ natureza, contraparte: c.chave, titulo: c.nome })
            }
          >
            {linha(c.nome, c.total_centavos)}
            <span className="sr-only">
              {`, ${c.quantidade} ${c.quantidade === 1 ? "transação" : "transações"}. Ver transações`}
            </span>
          </button>
        </li>
      ))}
      {a.outras_contrapartes_centavos > 0 ? (
        <li className="px-2 py-2 text-muted-foreground">
          {linha(
            `Outros (${a.outras_contrapartes_quantidade})`,
            a.outras_contrapartes_centavos
          )}
        </li>
      ) : null}
    </ul>
  )
}

function SemDados({ children }: { children?: ReactNode }) {
  return (
    <div className="space-y-3 py-8 text-center text-sm text-muted-foreground">
      <p>Sem dados no período.</p>
      {children}
    </div>
  )
}

// --- Acumulado: período atual × anterior (+ ritmo do orçamento) --------------------------------

function Acumulado({
  a,
  natureza,
}: {
  a: AnaliseNatureza
  natureza: Natureza
}) {
  const comOrcamento =
    natureza === "despesa" &&
    a.acumulado.some((p) => p.esperado_centavos != null)
  const series = useMemo<SerieLinha[]>(
    () => [
      {
        chave: "atual",
        nome: "Período atual",
        cor: "var(--primary)",
        largura: 2.5,
      },
      {
        chave: "anterior",
        nome: "Período anterior",
        cor: "var(--chart-cat-outras)",
        tracejada: true,
      },
      ...(comOrcamento
        ? [
            {
              chave: "esperado",
              nome: "Ritmo do orçamento",
              cor: "var(--chart-cat-4)",
              tracejada: true,
            },
          ]
        : []),
    ],
    [comOrcamento]
  )
  const dados = useMemo(
    () =>
      a.acumulado.map((p) => ({
        data: p.data,
        atual: p.atual_centavos,
        anterior: p.anterior_centavos,
        esperado: p.esperado_centavos,
      })),
    [a]
  )
  const detalhe = useCallback(
    (i: number) => {
      const p = a.acumulado[i]
      if (!p) return ""
      const ref = nota(`Anterior: até ${diaMes(addDias(a.anterior_inicio, i))}`)
      if (p.atual_centavos == null || p.anterior_centavos == null) return ref
      const dif = p.atual_centavos - p.anterior_centavos
      const sentido =
        dif === 0 ? "igual ao" : dif > 0 ? "acima do" : "abaixo do"
      return (
        nota(
          `${dif > 0 ? "▲" : dif < 0 ? "▼" : "="} ${formatBRL(Math.abs(dif))} ${sentido} período anterior`,
          true
        ) + ref
      )
    },
    [a]
  )
  if (a.total_centavos === 0 && a.anterior_centavos === 0) return <SemDados />
  return (
    <GraficoLinhas
      dados={dados}
      x="data"
      series={series}
      formatarX={diaMes}
      formatarRotulo={diaMes}
      formatarY={eixoBRL}
      formatarValor={formatBRL}
      detalheTooltip={detalhe}
      legenda
      altura={260}
      ariaLabel={`${NOMES[natureza].plural} acumuladas dia a dia no período atual e no anterior`}
    />
  )
}

// --- Receitas previstas × realizadas -----------------------------------------------------------

function PrevistoRealizado({ a }: { a: AnaliseNatureza }) {
  const dados = useMemo(
    () =>
      a.previsto.map((p) => ({
        mes: p.mes,
        previsto: p.previsto_centavos,
        recebido: p.realizado_centavos,
      })),
    [a]
  )
  const atual = mesAteHoje().inicio.slice(0, 7)
  const destaque = useMemo(
    () => ({
      serie: 1,
      cor: "var(--negative)",
      quando: (i: number) => {
        const p = a.previsto[i]
        return (
          p.previsto_centavos != null &&
          p.realizado_centavos < p.previsto_centavos
        )
      },
    }),
    [a]
  )
  const detalhe = useCallback(
    (i: number) => {
      const p = a.previsto[i]
      if (!p || p.previsto_centavos == null)
        return nota("Sem orçamento de receita neste mês")
      const dif = p.realizado_centavos - p.previsto_centavos
      const rel = p.previsto_centavos
        ? ` (${dif >= 0 ? "+" : "−"}${pct(Math.abs(dif) / p.previsto_centavos)})`
        : ""
      return (
        nota(
          `${dif >= 0 ? "▲ Acima" : "▼ Abaixo"} do previsto: ${formatBRL(Math.abs(dif))}${rel}`,
          true
        ) + (p.mes === atual ? nota("Mês em andamento") : "")
      )
    },
    [a, atual]
  )
  if (a.previsto.every((p) => p.previsto_centavos == null))
    return (
      <div className="space-y-3 py-8 text-center text-sm text-muted-foreground">
        <p>Nenhum orçamento de receita nos meses do período.</p>
        <Button asChild variant="outline" size="sm">
          <Link to="/orcamentos">
            Definir receitas previstas
            <ArrowRight aria-hidden />
          </Link>
        </Button>
      </div>
    )
  return (
    <div className="space-y-2">
      <GraficoBarrasAgrupadas
        dados={dados}
        x="mes"
        series={SERIES_PREVISTO}
        destaque={destaque}
        formatarX={mesAno}
        formatarRotulo={mesAno}
        formatarY={eixoBRL}
        formatarValor={formatBRL}
        detalheTooltip={detalhe}
        ariaLabel="Receitas previstas no orçamento e recebidas, mês a mês"
      />
      <p className="text-xs text-muted-foreground">
        Em vermelho, meses com recebimento abaixo do previsto. Previsões não
        entram como receita.
      </p>
    </div>
  )
}

const SERIES_PREVISTO = [
  { chave: "previsto", nome: "Previsto", cor: "var(--chart-cat-outras)" },
  { chave: "recebido", nome: "Recebido", cor: "var(--positive)" },
]
const SERIES_ORCAMENTO = [
  { chave: "orcado", nome: "Orçado", cor: "var(--chart-cat-outras)" },
  { chave: "gasto", nome: "Gasto", cor: "var(--chart-cat-1)" },
]

// --- Despesas × orçamento (mês do fim do período) ----------------------------------------------

function DespesasOrcamento({
  fim,
  rotulo,
}: {
  fim: string
  rotulo: Map<string, string>
}) {
  const [ano, mes] = fim.split("-").map(Number)
  const consumo = useConsumoOrcamentos(ano, mes)
  const [alvo, setAlvo] = useState<(AlvoDrilldown & { titulo: string }) | null>(
    null
  )
  const itens = useMemo(
    () =>
      (consumo.data?.itens ?? []).filter(
        (i) => i.tipo === "despesa" && !i.suprimido
      ),
    [consumo.data]
  )
  const dados = useMemo(
    () =>
      itens.map((i) => ({
        nome: rotulo.get(i.categoria_id) ?? i.categoria_id,
        orcado: i.limite_centavos,
        gasto: i.realizado_centavos,
      })),
    [itens, rotulo]
  )
  const destaque = useMemo(
    () => ({
      serie: 1,
      cor: "var(--negative)",
      quando: (i: number) =>
        itens[i].realizado_centavos > itens[i].limite_centavos,
    }),
    [itens]
  )
  const detalhe = useCallback(
    (i: number) => {
      const it = itens[i]
      if (!it) return ""
      const sobra = it.limite_centavos - it.realizado_centavos
      return (
        nota(
          sobra >= 0
            ? `Restam ${formatBRL(sobra)} · ${it.percentual}% utilizado`
            : `▲ Estourou ${formatBRL(-sobra)} · ${it.percentual}% utilizado`,
          true
        ) + nota("Clique para ver as transações")
      )
    },
    [itens]
  )
  const nomeMes = new Date(ano, mes - 1, 1).toLocaleDateString("pt-BR", {
    month: "long",
    year: "numeric",
  })
  return (
    <CardGrafico
      titulo="Despesas × orçamento"
      descricao={`Mês inteiro de ${nomeMes} (orçamento é mensal) · subcategorias somam na categoria`}
      acao={
        <Button asChild variant="ghost" size="sm">
          <Link to="/orcamentos">Ver orçamento</Link>
        </Button>
      }
    >
      <Estado carregando={consumo.isLoading} erro={consumo.isError}>
        {itens.length === 0 ? (
          <div className="space-y-3 py-8 text-center text-sm text-muted-foreground">
            <p>Nenhum orçamento de despesa em {nomeMes}.</p>
            <Button asChild variant="outline" size="sm">
              <Link to="/orcamentos">
                Criar orçamento
                <ArrowRight aria-hidden />
              </Link>
            </Button>
          </div>
        ) : (
          <div className="space-y-2">
            <GraficoBarrasAgrupadas
              dados={dados}
              x="nome"
              series={SERIES_ORCAMENTO}
              destaque={destaque}
              formatarX={curto}
              formatarY={eixoBRL}
              formatarValor={formatBRL}
              detalheTooltip={detalhe}
              onClique={(i) =>
                setAlvo({
                  tipo: "despesa",
                  categoriaId: itens[i].categoria_id,
                  titulo: dados[i].nome,
                })
              }
              ariaLabel={`Gasto e orçamento por categoria em ${nomeMes}`}
            />
            <p className="text-xs text-muted-foreground">
              Em vermelho, categorias acima do limite. Clique numa categoria
              para ver as transações.
            </p>
          </div>
        )}
      </Estado>
      <TransacoesOrcamentoDialog
        ano={ano}
        mes={mes}
        alvo={alvo}
        titulo={alvo?.titulo ?? ""}
        onFechar={() => setAlvo(null)}
      />
    </CardGrafico>
  )
}

// --- Média por dia da semana --------------------------------------------------------------------

function DiaDaSemana({ a }: { a: AnaliseNatureza }) {
  const medias = useMemo(
    () =>
      a.dias_semana.map((d) =>
        d.ocorrencias ? Math.round(d.total_centavos / d.ocorrencias) : 0
      ),
    [a]
  )
  const validos = a.dias_semana
    .map((d, i) => (d.ocorrencias ? i : -1))
    .filter((i) => i >= 0)
  const iMax = validos.reduce(
    (m, i) => (medias[i] > medias[m] ? i : m),
    validos[0] ?? 0
  )
  const iMin = validos.reduce(
    (m, i) => (medias[i] < medias[m] ? i : m),
    validos[0] ?? 0
  )
  const temDestaque = validos.length > 1 && medias[iMax] !== medias[iMin]
  const dados = useMemo(
    () => DIAS_CURTOS.map((dia, i) => ({ dia, media: medias[i] })),
    [medias]
  )
  const cores = useMemo(
    () =>
      medias.map((_, i) =>
        !temDestaque
          ? null
          : i === iMax
            ? "var(--negative)"
            : i === iMin
              ? "var(--positive)"
              : null
      ),
    [medias, temDestaque, iMax, iMin]
  )
  const detalhe = useCallback(
    (i: number) => {
      const d = a.dias_semana[i]
      const marca =
        temDestaque && i === iMax
          ? nota("Maior média", true)
          : temDestaque && i === iMin
            ? nota("Menor média", true)
            : ""
      return (
        marca +
        nota(
          `Total ${formatBRL(d.total_centavos)} em ${d.ocorrencias} ${DIAS[i].toLowerCase()}${d.ocorrencias === 1 ? "" : "s"}`
        )
      )
    },
    [a, temDestaque, iMax, iMin]
  )
  if (a.total_centavos <= 0) return <SemDados />
  return (
    <div className="space-y-2">
      <GraficoBarras
        dados={dados}
        x="dia"
        chave="media"
        nome="Média diária"
        cor="var(--chart-cat-outras)"
        cores={cores}
        formatarRotulo={(v) => DIAS[DIAS_CURTOS.indexOf(v)] ?? v}
        formatarY={eixoBRL}
        formatarValor={formatBRL}
        detalheTooltip={detalhe}
        altura={240}
        ariaLabel="Média de gastos por dia da semana no período"
      />
      {temDestaque ? (
        <p className="text-xs text-muted-foreground">
          Maior média:{" "}
          <strong className="font-medium text-foreground">{DIAS[iMax]}</strong>{" "}
          ({formatBRL(medias[iMax])}) · Menor:{" "}
          <strong className="font-medium text-foreground">{DIAS[iMin]}</strong>{" "}
          ({formatBRL(medias[iMin])}). Dias sem gasto contam na média.
        </p>
      ) : null}
    </div>
  )
}

// --- Abas ---------------------------------------------------------------------------------------

/** Evolução das receitas: colunas por período (granularidade escolhível). */
function EvolucaoReceitas({
  periodo,
  rotuloPeriodo,
}: {
  periodo: Periodo
  rotuloPeriodo: string
}) {
  const [gran, setGran] = useState<Granularidade>("semanal")
  const serie = useDashboardSeries(periodo, gran)
  const dados = useMemo(
    () =>
      (serie.data?.buckets ?? []).map((b) => ({
        inicio: b.inicio,
        recebido: b.entradas_centavos,
      })),
    [serie.data]
  )
  const rotulo = useCallback((v: string) => formatBucketLabel(v, gran), [gran])
  return (
    <CardGrafico
      titulo="Evolução das receitas"
      descricao={`Por ${PERIODO_LABEL[gran]} · ${rotuloPeriodo}`}
      acao={<SeletorGranularidade valor={gran} onChange={setGran} />}
    >
      <Estado
        carregando={serie.isLoading}
        erro={serie.isError}
        altura="h-[260px]"
      >
        {dados.every((d) => d.recebido === 0) ? (
          <SemDados />
        ) : (
          <GraficoBarras
            dados={dados}
            x="inicio"
            chave="recebido"
            nome="Recebido"
            cor="var(--positive)"
            formatarX={rotulo}
            formatarRotulo={rotulo}
            formatarY={eixoBRL}
            formatarValor={formatBRL}
            altura={260}
            ariaLabel={`Receitas por ${PERIODO_LABEL[gran]} no período`}
          />
        )}
      </Estado>
    </CardGrafico>
  )
}

/** Evolução das despesas: colunas empilhadas por categoria (mesmas cores da rosca). */
function EvolucaoDespesas({
  periodo,
  rotuloPeriodo,
  rotulo,
  onSelecionar,
}: {
  periodo: Periodo
  rotuloPeriodo: string
  rotulo: Map<string, string>
  onSelecionar: (c: CategoriaSelecionada) => void
}) {
  const [gran, setGran] = useState<Granularidade>("semanal")
  const serie = useDashboardSeries(periodo, gran)
  return (
    <CardGrafico
      titulo="Evolução das despesas"
      descricao={`Por ${PERIODO_LABEL[gran]}, por categoria · ${rotuloPeriodo}`}
      acao={<SeletorGranularidade valor={gran} onChange={setGran} />}
    >
      <Estado
        carregando={serie.isLoading}
        erro={serie.isError}
        altura="h-[280px]"
      >
        <BarrasEmpilhadasCategorias
          buckets={serie.data?.buckets ?? []}
          granularidade={gran}
          rotulo={rotulo}
          onSelecionar={onSelecionar}
        />
      </Estado>
    </CardGrafico>
  )
}

export function AbaReceitas({
  periodo,
  rotuloPeriodo,
  rotulo,
  oculto,
}: {
  periodo: Periodo
  rotuloPeriodo: string
  rotulo: Map<string, string>
  oculto: boolean
}) {
  const analise = useAnalise("receita", periodo)
  const a = analise.data
  const [filtro, setFiltro] = useState<FiltroAnalise | null>(null)
  const estado = { carregando: analise.isLoading, erro: analise.isError }
  return (
    <div className="space-y-4">
      <Kpis natureza="receita" analise={analise} oculto={oculto} />
      <div className="grid gap-4 @5xl:grid-cols-2">
        <div className="@5xl:col-span-2">
          <EvolucaoReceitas periodo={periodo} rotuloPeriodo={rotuloPeriodo} />
        </div>
        <CardGrafico
          titulo="Receitas por categoria"
          descricao={`${rotuloPeriodo} (sem transferências, resgates e aportes)`}
        >
          <Estado {...estado}>
            {a ? (
              <DistribuicaoCategorias
                gastos={a.por_categoria}
                rotulo={rotulo}
                ariaLabel="Distribuição das receitas por categoria no período"
                rotuloLista="Receitas por categoria"
                onSelecionar={(c) =>
                  setFiltro({
                    natureza: "receita",
                    categoria_id: c.id,
                    titulo: c.nome,
                  })
                }
              />
            ) : null}
          </Estado>
        </CardGrafico>
        <CardGrafico
          titulo="Principais fontes de receita"
          descricao="Quem mais pagou no período, como o banco identifica"
        >
          <Estado {...estado}>
            {a ? (
              <RankingContrapartes
                a={a}
                natureza="receita"
                onSelecionar={setFiltro}
              />
            ) : null}
          </Estado>
        </CardGrafico>
        <CardGrafico
          titulo="Previstas × realizadas"
          descricao="Orçamento de receita × recebido, meses inteiros do período"
        >
          <Estado {...estado}>{a ? <PrevistoRealizado a={a} /> : null}</Estado>
        </CardGrafico>
        <CardGrafico
          titulo="Receitas acumuladas"
          descricao="Recebido até cada dia, comparado ao período anterior"
        >
          <Estado {...estado}>
            {a ? <Acumulado a={a} natureza="receita" /> : null}
          </Estado>
        </CardGrafico>
      </div>
      <TransacoesAnaliseDialog
        filtro={filtro}
        inicio={periodo.inicio}
        fim={periodo.fim}
        onFechar={() => setFiltro(null)}
      />
    </div>
  )
}

export function AbaDespesas({
  periodo,
  rotuloPeriodo,
  rotulo,
  oculto,
}: {
  periodo: Periodo
  rotuloPeriodo: string
  rotulo: Map<string, string>
  oculto: boolean
}) {
  const analise = useAnalise("despesa", periodo)
  const a = analise.data
  const dashMes = useDashboard(mesAteHoje())
  const [filtro, setFiltro] = useState<FiltroAnalise | null>(null)
  const estado = { carregando: analise.isLoading, erro: analise.isError }
  const porCategoria = (c: CategoriaSelecionada) =>
    setFiltro({ natureza: "despesa", categoria_id: c.id, titulo: c.nome })
  // Meio de pagamento reaproveita a rosca de categorias: o "id" é o próprio nome do meio.
  const meios = useMemo(() => {
    const lista = a?.meios ?? []
    return {
      gastos: lista.map((m) => ({
        categoria_id: m.meio,
        total_centavos: m.total_centavos,
      })),
      rotulo: new Map(lista.map((m) => [m.meio, m.meio])),
      detalhe: new Map(
        lista
          .filter((m) => m.por_conta.length > 0)
          .map((m) => [
            m.meio,
            m.por_conta
              .map((c) => `${c.nome} ${formatBRL(c.total_centavos)}`)
              .join(" · "),
          ])
      ),
    }
  }, [a])
  return (
    <div className="space-y-4">
      <Kpis natureza="despesa" analise={analise} oculto={oculto} />
      <div className="grid gap-4 @5xl:grid-cols-2">
        <div className="@5xl:col-span-2">
          <EvolucaoDespesas
            periodo={periodo}
            rotuloPeriodo={rotuloPeriodo}
            rotulo={rotulo}
            onSelecionar={porCategoria}
          />
        </div>
        <CardGrafico
          titulo="Despesas por categoria"
          descricao={`${rotuloPeriodo} (sem transferências e investimentos; estornos abatem)`}
        >
          <Estado {...estado}>
            {a ? (
              <DistribuicaoCategorias
                gastos={a.por_categoria}
                rotulo={rotulo}
                onSelecionar={porCategoria}
              />
            ) : null}
          </Estado>
        </CardGrafico>
        <CardGrafico
          titulo="Maiores estabelecimentos"
          descricao="Para quem mais foi dinheiro no período"
        >
          <Estado {...estado}>
            {a ? (
              <RankingContrapartes
                a={a}
                natureza="despesa"
                onSelecionar={setFiltro}
              />
            ) : null}
          </Estado>
        </CardGrafico>
        <DespesasOrcamento fim={periodo.fim} rotulo={rotulo} />
        <CardGrafico
          titulo="Despesas acumuladas"
          descricao="Gasto até cada dia, comparado ao período anterior"
        >
          <Estado {...estado}>
            {a ? <Acumulado a={a} natureza="despesa" /> : null}
          </Estado>
        </CardGrafico>
        <CardGrafico
          titulo="Despesas por dia da semana"
          descricao={`Média diária · ${rotuloPeriodo}`}
        >
          <Estado {...estado}>{a ? <DiaDaSemana a={a} /> : null}</Estado>
        </CardGrafico>
        <CardGrafico
          titulo="Por meio de pagamento"
          descricao="Como o banco informa cada lançamento"
        >
          <Estado {...estado}>
            {a ? (
              <DistribuicaoCategorias
                gastos={meios.gastos}
                rotulo={meios.rotulo}
                detalhe={meios.detalhe}
                ariaLabel="Distribuição das despesas por meio de pagamento"
                rotuloLista="Despesas por meio de pagamento"
                onSelecionar={(c) =>
                  setFiltro({ natureza: "despesa", meio: c.id, titulo: c.nome })
                }
              />
            ) : null}
          </Estado>
        </CardGrafico>
        <div className="@5xl:col-span-2">
          <CardGrafico
            titulo="Cartões de crédito"
            descricao="Visão global das faturas, parcelas e limites"
            acao={
              <Button asChild variant="ghost" size="sm">
                <Link to="/faturas">Ver faturas</Link>
              </Button>
            }
          >
            <PainelCartoes saidasMes={dashMes.data?.saidas_centavos} />
          </CardGrafico>
        </div>
      </div>
      <TransacoesAnaliseDialog
        filtro={filtro}
        inicio={periodo.inicio}
        fim={periodo.fim}
        onFechar={() => setFiltro(null)}
      />
    </div>
  )
}
