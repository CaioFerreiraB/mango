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
  type ConsumoLinha,
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
  type Visao,
} from "@/lib/api/dashboard"
import { useConsumoOrcamentos, type AlvoDrilldown } from "@/lib/api/orcamentos"
import {
  addDias,
  formatBRL,
  formatBucketLabel,
  mesAteHoje,
  ultimos6MesesCompletos,
} from "@/lib/format"
import { cn } from "@/lib/utils"

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

/** Os quatro KPIs da aba, um widget cada (ids `rec-…`/`desp-…` do catálogo). */
function kpisAnalise(
  natureza: Natureza,
  analise: ReturnType<typeof useAnalise>,
  tendencia: ReturnType<typeof useDashboardSeries>,
  oculto: boolean
): Record<string, () => ReactNode> {
  const p = natureza === "receita" ? "rec" : "desp"
  const ids = [
    `${p}-total`,
    `${p}-anterior`,
    `${p}-media`,
    natureza === "receita" ? "rec-previsto" : "desp-orcamento",
  ]
  const a = analise.data
  if (analise.isError || !a) {
    const no = analise.isError
      ? () => <ErroCard />
      : () => <Skeleton className="h-28 w-full rounded-xl" />
    return Object.fromEntries(ids.map((id) => [id, no]))
  }
  const n = NOMES[natureza]
  const anterior = `${diaMes(a.anterior_inicio)} a ${diaMes(a.anterior_fim)}`
  const meses = a.previsto.filter((p) => p.previsto_centavos != null)
  const orcado = meses.reduce((s, p) => s + (p.previsto_centavos ?? 0), 0)
  const realizadoOrcado = meses.reduce((s, p) => s + p.realizado_centavos, 0)
  const dias = a.dias_semana.reduce((s, d) => s + d.ocorrencias, 0)
  return {
    [ids[0]]: () => (
      <KpiCard
        label={`${n.acao} no período`}
        centavos={a.total_centavos}
        delta={variacao(a.total_centavos, a.anterior_centavos)}
        tituloDelta={`Comparado a ${anterior}`}
        serie={tendencia.data?.buckets}
        campo={natureza === "receita" ? "entradas_centavos" : "saidas_centavos"}
        oculto={oculto}
      />
    ),
    [ids[1]]: () => (
      <KpiCard
        label="Período anterior"
        centavos={a.anterior_centavos}
        rodape={anterior}
        oculto={oculto}
      />
    ),
    [ids[2]]: () =>
      natureza === "receita" ? (
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
      ),
    [ids[3]]: () => (
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
    ),
  }
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
  // "Outros" pode passar da maior contraparte (ou ser negativo, com estornos): a escala usa o
  // maior dos dois e a largura fica em [1%, 100%].
  const max = Math.max(
    a.contrapartes[0].total_centavos,
    a.outras_contrapartes_centavos
  )
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
          style={{
            width: `${Math.min(100, Math.max((valor / max) * 100, 1))}%`,
          }}
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
      {a.outras_contrapartes_centavos !== 0 ? (
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
  // Vazio só sem nenhum ponto ≠ 0 (compra + estorno no mesmo período termina em 0, mas houve
  // movimento a mostrar).
  const temValor = a.acumulado.some(
    (p) => (p.atual_centavos ?? 0) !== 0 || (p.anterior_centavos ?? 0) !== 0
  )
  if (!temValor) return <SemDados />
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
// --- Despesas × orçamento (mês do fim do período) ----------------------------------------------

/* Heatmap de uso do orçamento: azul padrão (--positive) cheio até 25%, desbotando até 100%;
   acima disso, framboesa clara → a framboesa de despesa (--negative) cheio no pior caso. Faixas
   discretas (legenda legível); mistura ≤ 60% mantém texto --foreground em AA nos dois temas
   (≥ 5.1:1), e os degraus cheios usam o --*-foreground da cor (4.69:1 no azul, 5.4:1 na framboesa). */
const FAIXAS_USO = [
  {
    ate: 0.25,
    rotulo: "até 25%",
    fundo: "var(--positive)",
    texto: "text-positive-foreground",
  },
  {
    ate: 0.5,
    rotulo: "até 50%",
    fundo: "color-mix(in oklab, var(--positive) 60%, var(--card))",
  },
  {
    ate: 0.75,
    rotulo: "até 75%",
    fundo: "color-mix(in oklab, var(--positive) 38%, var(--card))",
  },
  {
    ate: 1,
    rotulo: "até 100%",
    fundo: "color-mix(in oklab, var(--positive) 18%, var(--card))",
  },
  {
    ate: 1.1,
    rotulo: "até 110%",
    fundo: "color-mix(in oklab, var(--negative) 28%, var(--card))",
  },
  {
    ate: 1.3,
    rotulo: "até 130%",
    fundo: "color-mix(in oklab, var(--negative) 55%, var(--card))",
  },
  {
    ate: Infinity,
    rotulo: "acima de 130%",
    fundo: "var(--negative)",
    texto: "text-negative-foreground",
  },
]

function faixaUso(realizado: number, limite: number) {
  const uso = limite > 0 ? realizado / limite : realizado > 0 ? Infinity : 0
  return FAIXAS_USO.find((f) => uso <= f.ate)!
}

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
  // Mais usado primeiro: o que pede atenção abre a grade.
  const itens = useMemo(
    () =>
      (consumo.data?.itens ?? [])
        .filter((i) => i.tipo === "despesa" && !i.suprimido)
        .sort((a, b) => b.percentual - a.percentual),
    [consumo.data]
  )
  // Resumo do diálogo lido dos dados atuais (refetch com o diálogo aberto atualiza); a categoria
  // é única por mês/tipo. Linha sumiu (orçamento removido) → sem resumo.
  const linhaAlvo =
    alvo && itens.find((i) => i.categoria_id === alvo.categoriaId)
  const consumoDoAlvo: ConsumoLinha | undefined = linhaAlvo
    ? {
        realizado: linhaAlvo.realizado_centavos,
        limite: linhaAlvo.limite_centavos,
        percentual: linhaAlvo.percentual,
      }
    : undefined
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
          <div className="space-y-3">
            <ul
              className="grid grid-cols-[repeat(auto-fill,minmax(6rem,1fr))] gap-1.5"
              aria-label={`Uso do orçamento por categoria em ${nomeMes}`}
            >
              {itens.map((it) => {
                const nome = rotulo.get(it.categoria_id) ?? it.categoria_id
                const faixa = faixaUso(
                  it.realizado_centavos,
                  it.limite_centavos
                )
                const sobra = it.limite_centavos - it.realizado_centavos
                const resumo =
                  sobra >= 0
                    ? `restam ${formatBRL(sobra)}`
                    : `estourou ${formatBRL(-sobra)}`
                return (
                  <li key={it.orcamento_mensal_id}>
                    <button
                      type="button"
                      title={`${nome} · ${formatBRL(it.realizado_centavos)} de ${formatBRL(it.limite_centavos)} · ${resumo}`}
                      aria-label={`${nome}: ${it.percentual}% usado, ${formatBRL(it.realizado_centavos)} de ${formatBRL(it.limite_centavos)}, ${resumo}. Ver transações`}
                      style={{ background: faixa.fundo }}
                      className={cn(
                        "flex aspect-square w-full flex-col justify-between rounded-md p-2.5 text-left transition-[filter] outline-none hover:brightness-95 focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-card dark:hover:brightness-110",
                        faixa.texto ?? "text-foreground"
                      )}
                      onClick={() =>
                        setAlvo({
                          tipo: "despesa",
                          categoriaId: it.categoria_id,
                          titulo: nome,
                        })
                      }
                    >
                      <span className="line-clamp-2 text-xs font-medium break-words">
                        {nome}
                      </span>
                      <span>
                        <span className="block text-xl font-semibold tabular-nums">
                          {it.percentual}%
                        </span>
                        <span className="block truncate text-[11px] tabular-nums">
                          {formatBRL(it.realizado_centavos)}
                        </span>
                      </span>
                    </button>
                  </li>
                )
              })}
            </ul>
            <div
              className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground"
              aria-hidden
            >
              {FAIXAS_USO.map((f) => (
                <span key={f.rotulo} className="flex items-center gap-1">
                  <span
                    className="size-3 rounded-sm ring-1 ring-border"
                    style={{ background: f.fundo }}
                  />
                  {f.rotulo}
                </span>
              ))}
            </div>
            <p className="text-xs text-muted-foreground">
              Azul: dentro do limite · framboesa: acima dele. Escolha uma
              categoria para ver as transações.
            </p>
          </div>
        )}
      </Estado>
      <TransacoesOrcamentoDialog
        ano={ano}
        mes={mes}
        alvo={alvo}
        titulo={alvo?.titulo ?? ""}
        consumo={consumoDoAlvo}
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
  visao,
}: {
  periodo: Periodo
  rotuloPeriodo: string
  visao: Visao
}) {
  const [gran, setGran] = useState<Granularidade>("semanal")
  const serie = useDashboardSeries(periodo, gran, visao)
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
  visao,
}: {
  periodo: Periodo
  rotuloPeriodo: string
  rotulo: Map<string, string>
  onSelecionar: (c: CategoriaSelecionada) => void
  visao: Visao
}) {
  const [gran, setGran] = useState<Granularidade>("semanal")
  const serie = useDashboardSeries(periodo, gran, visao)
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

type PropsAba = {
  periodo: Periodo
  rotuloPeriodo: string
  rotulo: Map<string, string>
  oculto: boolean
  visao: Visao
  /** Grade personalizável do dashboard (mesma da aba Geral) que posiciona os widgets. */
  grade: (widgets: Record<string, () => ReactNode>) => ReactNode
}

export function AbaReceitas({
  periodo,
  rotuloPeriodo,
  rotulo,
  oculto,
  visao,
  grade,
}: PropsAba) {
  const analise = useAnalise("receita", periodo, visao)
  // Tendência de 6 meses: mesma query compartilhada com os cards da aba Geral.
  const tendencia = useDashboardSeries(
    ultimos6MesesCompletos(),
    "mensal",
    visao
  )
  const a = analise.data
  const [filtro, setFiltro] = useState<FiltroAnalise | null>(null)
  const estado = { carregando: analise.isLoading, erro: analise.isError }
  const widgets: Record<string, () => ReactNode> = {
    ...kpisAnalise("receita", analise, tendencia, oculto),
    "rec-evolucao": () => (
      <EvolucaoReceitas
        periodo={periodo}
        rotuloPeriodo={rotuloPeriodo}
        visao={visao}
      />
    ),
    "rec-categorias": () => (
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
    ),
    "rec-fontes": () => (
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
    ),
    "rec-previstas": () => (
      <CardGrafico
        titulo="Previstas × realizadas"
        descricao="Orçamento de receita × recebido, meses inteiros do período"
      >
        <Estado {...estado}>{a ? <PrevistoRealizado a={a} /> : null}</Estado>
      </CardGrafico>
    ),
    "rec-acumulado": () => (
      <CardGrafico
        titulo="Receitas acumuladas"
        descricao="Recebido até cada dia, comparado ao período anterior"
      >
        <Estado {...estado}>
          {a ? <Acumulado a={a} natureza="receita" /> : null}
        </Estado>
      </CardGrafico>
    ),
  }
  return (
    <>
      {grade(widgets)}
      <TransacoesAnaliseDialog
        filtro={filtro}
        inicio={periodo.inicio}
        fim={periodo.fim}
        visao={visao}
        onFechar={() => setFiltro(null)}
      />
    </>
  )
}

export function AbaDespesas({
  periodo,
  rotuloPeriodo,
  rotulo,
  oculto,
  visao,
  grade,
}: PropsAba) {
  const analise = useAnalise("despesa", periodo, visao)
  const tendencia = useDashboardSeries(
    ultimos6MesesCompletos(),
    "mensal",
    visao
  )
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
  const widgets: Record<string, () => ReactNode> = {
    ...kpisAnalise("despesa", analise, tendencia, oculto),
    "desp-evolucao": () => (
      <EvolucaoDespesas
        periodo={periodo}
        rotuloPeriodo={rotuloPeriodo}
        rotulo={rotulo}
        onSelecionar={porCategoria}
        visao={visao}
      />
    ),
    "desp-categorias": () => (
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
    ),
    "desp-maiores": () => (
      <CardGrafico
        titulo="Maiores despesas"
        descricao="Somadas pela descrição da transação no período"
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
    ),
    "desp-orcamento-categorias": () => (
      <DespesasOrcamento fim={periodo.fim} rotulo={rotulo} />
    ),
    "desp-acumulado": () => (
      <CardGrafico
        titulo="Despesas acumuladas"
        descricao="Gasto até cada dia, comparado ao período anterior"
      >
        <Estado {...estado}>
          {a ? <Acumulado a={a} natureza="despesa" /> : null}
        </Estado>
      </CardGrafico>
    ),
    "desp-dia-semana": () => (
      <CardGrafico
        titulo="Despesas por dia da semana"
        descricao={`Média diária · ${rotuloPeriodo}`}
      >
        <Estado {...estado}>{a ? <DiaDaSemana a={a} /> : null}</Estado>
      </CardGrafico>
    ),
    "desp-meios": () => (
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
    ),
    "desp-cartoes": () => (
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
    ),
  }
  return (
    <>
      {grade(widgets)}
      <TransacoesAnaliseDialog
        filtro={filtro}
        inicio={periodo.inicio}
        fim={periodo.fim}
        visao={visao}
        onFechar={() => setFiltro(null)}
      />
    </>
  )
}
