import { ChevronLeft, ChevronRight, List, TrendingUp } from "lucide-react"
import { useMemo, useState } from "react"

import { Valor } from "@/components/common/valor"
import { CardGrafico } from "@/components/dashboard/card-grafico"
import { TransacoesPeriodoDialog } from "@/components/dashboard/transacoes-dialog"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import {
  useDashboardSeries,
  type SerieBucket,
  type Visao,
} from "@/lib/api/dashboard"
import {
  corTexto,
  intensidade,
  misturar,
  PISO,
  semanasDoMes,
} from "@/lib/calendario-calor"
import { useTemaGrafico } from "@/lib/echart-tema"
import { hojeISO } from "@/lib/format"
import { cn } from "@/lib/utils"

type Modo = "tudo" | "despesas" | "receitas" | "investimentos"

/** Valor do dia em cada modo. "Tudo" = resultado (entradas − saídas), a mesma conta dos cards:
 *  investimento fica de fora (aporte não é gasto) e aparece no painel do dia. */
const MODOS: Record<
  Modo,
  { rotulo: string; descricao: string; valor: (b: SerieBucket) => number }
> = {
  tudo: {
    rotulo: "Tudo",
    descricao: "resultado do dia (entradas − saídas)",
    valor: (b) => b.resultado_centavos,
  },
  despesas: {
    rotulo: "Despesas",
    descricao: "despesas do dia",
    valor: (b) => -b.saidas_centavos,
  },
  receitas: {
    rotulo: "Receitas",
    descricao: "receitas do dia",
    valor: (b) => b.entradas_centavos,
  },
  investimentos: {
    rotulo: "Investimentos",
    descricao: "aportes − resgates do dia",
    valor: (b) => b.investido_centavos,
  },
}

const DIAS_SEMANA = ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"]
const DIAS_SEMANA_LONGO = [
  "domingo",
  "segunda",
  "terça",
  "quarta",
  "quinta",
  "sexta",
  "sábado",
]

// Célula: resumo compacto ("-R$ 1,2 mil"); o valor exato mora no painel do dia.
const compacto = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  notation: "compact",
  maximumFractionDigits: 1,
  signDisplay: "exceptZero",
})
const brl = (centavos: number) => compacto.format(centavos / 100)

const dataLonga = (iso: string) => {
  const d = new Date(`${iso}T12:00:00`)
  return `${DIAS_SEMANA_LONGO[d.getDay()]}, ${d.toLocaleDateString("pt-BR", { day: "numeric", month: "long" })}`
}

/** Calendário de calor do mês do fim do período: cada dia colorido numa escala contínua do laranja
 *  de despesa (mais negativo) ao azul padrão (mais positivo); clicar num dia mostra o detalhe. */
export function CalendarioCalor({ fim, visao }: { fim: string; visao: Visao }) {
  const hoje = hojeISO()
  // Mês navegado pelas setas; trocar o período do dashboard (`fim`) volta para o mês dele.
  const [nav, setNav] = useState<{ de: string; ym: string } | null>(null)
  const ym = nav?.de === fim ? nav.ym : fim.slice(0, 7)
  const [ano, mes] = ym.split("-").map(Number)
  const primeiro = `${ym}-01`
  const ultimo = `${ym}-${new Date(ano, mes, 0).getDate()}`
  const serie = useDashboardSeries(
    { inicio: primeiro, fim: ultimo },
    "diaria",
    visao
  )
  const [modo, setModo] = useState<Modo>("tudo")
  const [escolhido, setSelecionado] = useState<string | null>(null)
  const selecionado = escolhido?.startsWith(ym) ? escolhido : null
  const [listaAberta, setListaAberta] = useState(false)
  const tema = useTemaGrafico()

  const irPara = (alvo: string, dia: string | null = null) => {
    setNav({ de: fim, ym: alvo })
    setSelecionado(dia)
  }
  const mover = (delta: number) => {
    const d = new Date(ano, mes - 1 + delta, 1)
    irPara(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`)
  }

  const porDia = useMemo(
    () =>
      new Map(
        (serie.data?.buckets ?? [])
          .filter((b) => b.inicio.startsWith(ym))
          .map((b) => [b.inicio, b])
      ),
    [serie.data, ym]
  )
  const semanas = useMemo(() => semanasDoMes(ano, mes), [ano, mes])
  const valorDe = (iso: string) => {
    const b = porDia.get(iso)
    return b ? MODOS[modo].valor(b) : 0
  }
  // Fora do modo Investimentos, aporte/resgate não entra na cor (ex.: "Tudo" = entradas − saídas,
  // como o card Resultado): o dia ganha só uma marca.
  const marcarInvest = modo !== "investimentos"
  const investiu = (iso: string) =>
    marcarInvest && (porDia.get(iso)?.investido_centavos ?? 0) !== 0
  const algumInvest =
    marcarInvest && [...porDia.values()].some((b) => b.investido_centavos !== 0)
  const movimentou = (iso: string) => {
    const b = porDia.get(iso)
    return (
      !!b &&
      (b.entradas_centavos !== 0 ||
        b.saidas_centavos !== 0 ||
        b.investido_centavos !== 0)
    )
  }
  const valores = [...porDia.values()].map(MODOS[modo].valor)
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

  const nomeMes = new Date(ano, mes - 1, 1).toLocaleDateString("pt-BR", {
    month: "long",
    year: "numeric",
  })
  // Painel: o dia escolhido ou, sem escolha, o mês inteiro.
  const doPainel = selecionado
    ? [porDia.get(selecionado)].filter((b) => b != null)
    : [...porDia.values()]
  const soma = (f: (b: SerieBucket) => number) =>
    doPainel.reduce((s, b) => s + f(b), 0)

  const navegacao = (
    <div className="flex items-center justify-between gap-2">
      <div className="flex items-center gap-1">
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={() => mover(-1)}
          aria-label="Mês anterior"
        >
          <ChevronLeft aria-hidden />
        </Button>
        <h3
          aria-live="polite"
          className="min-w-36 text-center text-sm font-medium first-letter:uppercase"
        >
          {nomeMes}
        </h3>
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={() => mover(1)}
          aria-label="Próximo mês"
        >
          <ChevronRight aria-hidden />
        </Button>
      </div>
      <Button
        variant="outline"
        size="sm"
        onClick={() => irPara(hoje.slice(0, 7), hoje)}
        disabled={selecionado === hoje}
      >
        Hoje
      </Button>
    </div>
  )

  return (
    <CardGrafico
      titulo="Calendário do mês"
      descricao={`${MODOS[modo].descricao[0].toUpperCase()}${MODOS[modo].descricao.slice(1)} · clique num dia para o detalhe`}
      acao={
        <ToggleGroup
          type="single"
          size="sm"
          variant="outline"
          spacing={0}
          value={modo}
          onValueChange={(v) => v && setModo(v as Modo)}
          aria-label="O que colorir no calendário"
        >
          {(Object.keys(MODOS) as Modo[]).map((m) => (
            <ToggleGroupItem key={m} value={m}>
              {MODOS[m].rotulo}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      }
    >
      {serie.isLoading ? (
        <div className="space-y-3">
          {navegacao}
          <Skeleton className="h-80 w-full" />
        </div>
      ) : serie.isError ? (
        <div className="space-y-3">
          {navegacao}
          <p className="py-8 text-center text-sm text-muted-foreground">
            Não foi possível carregar este mês.
          </p>
        </div>
      ) : (
        <div className="grid gap-6 @3xl:grid-cols-[minmax(0,1fr)_15rem]">
          <div className="min-w-0 space-y-3">
            {navegacao}
            <table className="w-full table-fixed border-separate border-spacing-1.5">
              <caption className="sr-only">
                {`Calendário de ${nomeMes}: ${MODOS[modo].descricao}`}
              </caption>
              <thead>
                <tr>
                  {DIAS_SEMANA.map((d, i) => (
                    <th
                      key={d}
                      scope="col"
                      abbr={DIAS_SEMANA_LONGO[i]}
                      className="pb-1 text-xs font-medium text-muted-foreground"
                    >
                      {d}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {semanas.map((semana) => (
                  <tr key={semana.find(Boolean)}>
                    {semana.map((iso, i) =>
                      iso ? (
                        <td key={iso} className="p-0">
                          <Dia
                            iso={iso}
                            valor={valorDe(iso)}
                            temMovimento={movimentou(iso)}
                            investiu={investiu(iso)}
                            estilo={
                              iso > hoje && !movimentou(iso)
                                ? {
                                    background: tema.superficie,
                                    color: tema.textoSec,
                                  }
                                : estilo(valorDe(iso))
                            }
                            hoje={iso === hoje}
                            selecionado={iso === selecionado}
                            rotuloModo={MODOS[modo].rotulo.toLowerCase()}
                            onClick={() =>
                              setSelecionado((s) => (s === iso ? null : iso))
                            }
                          />
                        </td>
                      ) : (
                        <td key={`vazio-${i}`} aria-hidden />
                      )
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
              {algumInvest ? (
                <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <TrendingUp className="size-3.5" aria-hidden />
                  Dia com aporte ou resgate
                </span>
              ) : (
                <span />
              )}
              {maxPos || maxNeg ? (
                <Legenda
                  maxPos={maxPos}
                  maxNeg={maxNeg}
                  superficie={tema.superficie}
                  positivo={tema.positivo}
                  negativo={tema.negativo}
                />
              ) : (
                <p className="text-sm text-muted-foreground">
                  Nada em {MODOS[modo].rotulo.toLowerCase()} neste mês.
                </p>
              )}
            </div>
          </div>
          <section
            aria-live="polite"
            aria-label="Detalhe"
            className="flex flex-col gap-3 rounded-lg bg-muted/40 p-4"
          >
            <h3 className="text-sm font-medium first-letter:uppercase">
              {selecionado ? dataLonga(selecionado) : `Total de ${nomeMes}`}
            </h3>
            <dl className="space-y-2 text-sm">
              <Linha
                rotulo="Receitas"
                centavos={soma((b) => b.entradas_centavos)}
                destaque={modo === "receitas"}
              />
              <Linha
                rotulo="Despesas"
                centavos={-soma((b) => b.saidas_centavos)}
                destaque={modo === "despesas"}
              />
              <Linha
                rotulo="Investido"
                centavos={soma((b) => b.investido_centavos)}
                destaque={modo === "investimentos"}
              />
              <div className="border-t pt-2">
                <Linha
                  rotulo="Resultado"
                  centavos={soma((b) => b.resultado_centavos)}
                  destaque={modo === "tudo"}
                />
              </div>
            </dl>
            <div className="mt-auto space-y-2 pt-2">
              <Button
                variant="outline"
                size="sm"
                className="w-full"
                onClick={() => setListaAberta(true)}
              >
                <List aria-hidden />
                {selecionado
                  ? "Ver lançamentos do dia"
                  : "Ver lançamentos do mês"}
              </Button>
              {selecionado ? (
                <Button
                  variant="ghost"
                  size="sm"
                  className="w-full text-muted-foreground"
                  onClick={() => setSelecionado(null)}
                >
                  Ver o total do mês
                </Button>
              ) : null}
            </div>
          </section>
        </div>
      )}
      <TransacoesPeriodoDialog
        periodo={
          listaAberta
            ? {
                inicio: selecionado ?? primeiro,
                fim: selecionado ?? ultimo,
                titulo: selecionado
                  ? `Lançamentos de ${dataLonga(selecionado)}`
                  : `Lançamentos de ${nomeMes}`,
              }
            : null
        }
        visao={visao}
        onFechar={() => setListaAberta(false)}
      />
    </CardGrafico>
  )
}

function Dia({
  iso,
  valor,
  temMovimento,
  investiu,
  estilo,
  hoje,
  selecionado,
  rotuloModo,
  onClick,
}: {
  iso: string
  valor: number
  temMovimento: boolean
  investiu: boolean
  estilo: { background: string; color: string }
  hoje: boolean
  selecionado: boolean
  rotuloModo: string
  onClick: () => void
}) {
  const dia = Number(iso.slice(8))
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selecionado}
      aria-label={`${dataLonga(iso)}${hoje ? " (hoje)" : ""}: ${temMovimento ? `${rotuloModo} ${brl(valor)}` : "sem movimento"}${investiu ? ", com aporte ou resgate" : ""}`}
      style={estilo}
      className={cn(
        "flex h-12 w-full flex-col justify-between rounded-md p-1.5 text-left ring-1 ring-border/70 transition-[filter,box-shadow] outline-none ring-inset hover:brightness-95 focus-visible:ring-2 focus-visible:ring-ring @xl:h-16 @xl:p-2 dark:hover:brightness-110",
        selecionado &&
          "shadow-[0_0_0_2px_var(--color-card),0_0_0_3.5px_var(--color-primary)]"
      )}
    >
      <span className="flex items-start justify-between gap-1">
        <span
          className={cn(
            "text-xs font-semibold tabular-nums",
            hoje &&
              "-mx-1 rounded-full bg-primary px-1.5 text-primary-foreground"
          )}
        >
          {dia}
        </span>
        {investiu ? (
          <TrendingUp className="size-3.5 shrink-0 opacity-80" aria-hidden />
        ) : null}
      </span>
      {valor ? (
        <span className="hidden truncate text-[11px] font-medium tabular-nums @xl:block">
          {brl(valor)}
        </span>
      ) : null}
    </button>
  )
}

function Linha({
  rotulo,
  centavos,
  destaque,
}: {
  rotulo: string
  centavos: number
  destaque: boolean
}) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className={destaque ? "font-medium" : "text-muted-foreground"}>
        {rotulo}
      </dt>
      <dd>
        <Valor
          centavos={centavos}
          sinal
          className={cn("tabular-nums", destaque && "text-base font-semibold")}
        />
      </dd>
    </div>
  )
}

/** Escala contínua: o extremo negativo à esquerda, zero na superfície, o positivo à direita. Só
 *  desenha os braços que o mês tem (só despesas → só o laranja). */
function Legenda({
  maxPos,
  maxNeg,
  superficie,
  positivo,
  negativo,
}: {
  maxPos: number
  maxNeg: number
  superficie: string
  positivo: string
  negativo: string
}) {
  // Só os tons que as células usam: do cheio até o piso de cada lado, sem a superfície pura
  // (zero) no meio — os dois pisos se emendam suavemente no centro.
  const fraco = (cor: string) => misturar(superficie, cor, PISO)
  const paradas =
    maxNeg && maxPos
      ? `${negativo} 0%, ${fraco(negativo)} 45%, ${fraco(positivo)} 55%, ${positivo} 100%`
      : maxNeg
        ? `${negativo}, ${fraco(negativo)}`
        : `${fraco(positivo)}, ${positivo}`
  return (
    <div
      className="flex items-center justify-end gap-2 text-xs text-muted-foreground tabular-nums"
      aria-hidden
    >
      <span>{maxNeg ? brl(-maxNeg) : "R$ 0"}</span>
      <span
        className="h-1.5 w-32 rounded-full"
        style={{
          background: `linear-gradient(to right, ${paradas})`,
        }}
      />
      <span>{maxPos ? brl(maxPos) : "R$ 0"}</span>
    </div>
  )
}
