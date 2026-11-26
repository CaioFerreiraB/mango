import {
  ChevronLeft,
  ChevronRight,
  CircleDashed,
  ListFilter,
  PiggyBank,
  Settings2,
  Wand2,
  X,
  type LucideIcon,
} from "lucide-react"
import {
  createElement,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type MouseEvent,
  type ReactNode,
  type RefObject,
} from "react"
import { toast } from "sonner"

import { EmptyState } from "@/components/common/empty-state"
import { CardDestaque } from "@/components/common/kpi"
import { PageHeader } from "@/components/common/page-header"
import { Valor } from "@/components/common/valor"
import { ConfigurarOrcamentoPadraoDialog } from "@/components/orcamentos/configurar-orcamento-padrao-dialog"
import { EditarMesDialog } from "@/components/orcamentos/editar-mes-dialog"
import { TransacoesTabela } from "@/components/transacoes/transacoes-tabela"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useIconeCategoria } from "@/lib/api/categoria-icones"
import { useMapaCategorias } from "@/lib/api/categorias"
import {
  useConsumoOrcamentos,
  useMaterializarMes,
  useTransacoesDoOrcamento,
  type AlvoDrilldown,
  type OrcamentoConsumoItem,
  type TipoOrcamento,
} from "@/lib/api/orcamentos"
import { formatMesAno, hojeISO } from "@/lib/format"
import { cn } from "@/lib/utils"

// Três degraus de consumo, nos tokens de estado do app: sucesso até 75%, aviso a partir daí,
// negativo (framboesa) ao estourar. A cor nunca é o único sinal (o % e a barra
// também informam). Só se aplica à despesa: receita não tem conceito de "estourar".
// Não usa o accent: com o preset rosa ele quase repete a framboesa de "estourou".
function corAlerta(alerta: number | null): string {
  if (alerta === null) return "bg-success"
  if (alerta >= 100) return "bg-negative"
  if (alerta >= 75) return "bg-warning"
  return "bg-success"
}

/** Rótulos por aba: despesa tem teto (limite/gasto); receita e investimento são metas a atingir. */
const ROTULOS: Record<
  TipoOrcamento,
  {
    aba: string
    orcado: string
    orcadoTotal: string
    realizado: string
    realizadoTotal: string
    restanteTotal: string
    anel: string
  }
> = {
  despesa: {
    aba: "Despesas",
    orcado: "Orçado",
    orcadoTotal: "Total orçado",
    realizado: "Gasto",
    realizadoTotal: "Gasto até agora",
    restanteTotal: "Restante",
    anel: "utilizado",
  },
  investimento: {
    aba: "Investimentos",
    orcado: "Meta",
    orcadoTotal: "Meta de aporte",
    realizado: "Aportado",
    realizadoTotal: "Aportado até agora",
    restanteTotal: "Restante pra meta",
    anel: "aportado",
  },
  receita: {
    aba: "Receitas",
    orcado: "Meta",
    orcadoTotal: "Meta total",
    realizado: "Recebido",
    realizadoTotal: "Recebido até agora",
    restanteTotal: "Restante pra meta",
    anel: "recebido",
  },
}

const TIPOS: TipoOrcamento[] = ["despesa", "investimento", "receita"]

export function OrcamentosPage() {
  const hoje = hojeISO()
  const anoAtual = Number(hoje.slice(0, 4))
  const mesAtual = Number(hoje.slice(5, 7))
  const [ano, setAno] = useState(anoAtual)
  const [mes, setMes] = useState(mesAtual)
  // Linha cujas transações estão abertas (uma por vez na página); fecha ao trocar de mês.
  const [alvo, setAlvo] = useState<AlvoDrilldown | null>(null)
  const consumo = useConsumoOrcamentos(ano, mes)
  const noMesAtual = ano === anoAtual && mes === mesAtual
  const mesEhPassado = ano < anoAtual || (ano === anoAtual && mes < mesAtual)

  function mudarMes(delta: number) {
    const total = ano * 12 + (mes - 1) + delta
    setAno(Math.floor(total / 12))
    setMes((total % 12) + 1)
    setAlvo(null)
  }

  const rotuloMes = formatMesAno(`${ano}-${String(mes).padStart(2, "0")}-01`)
  // `itens` inclui linhas suprimidas (removidas só deste mês) — só "Editar mês" precisa delas
  // (pra oferecer "restaurar"); a Visão Geral (resumo + tabela) as esconde.
  const itens = consumo.data?.itens ?? []
  const visiveis = itens.filter((i) => !i.suprimido)
  const naoPlanejado: Record<TipoOrcamento, number> = {
    despesa: consumo.data?.nao_planejado_despesa_centavos ?? 0,
    investimento: consumo.data?.nao_planejado_investimento_centavos ?? 0,
    receita: consumo.data?.nao_planejado_receita_centavos ?? 0,
  }
  const secao = { ano, mes, rotuloMes, alvo, onAlvo: setAlvo }

  return (
    <div className="space-y-6">
      <PageHeader
        titulo="Orçamento"
        descricao="Limite mensal por categoria, com alertas em 50%, 75%, 90% e 100%."
        acoes={
          <>
            <EditarMesDialog
              itens={itens}
              ano={ano}
              mes={mes}
              disabled={itens.length === 0}
            />
            {/* No mobile o botão reaparece embaixo da lista de categorias. */}
            <div className="hidden sm:block">
              <ConfigurarOrcamentoPadraoDialog />
            </div>
          </>
        }
      />

      {/* Controle da página: o mês vale para as três abas. */}
      <div className="flex w-fit items-center gap-1 rounded-md border p-0.5">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => mudarMes(-1)}
          aria-label="Mês anterior"
        >
          <ChevronLeft className="size-4" />
        </Button>
        <span
          className="min-w-36 text-center text-sm font-medium first-letter:uppercase"
          aria-live="polite"
        >
          {rotuloMes}
        </span>
        <Button
          variant="ghost"
          size="icon"
          onClick={() => mudarMes(1)}
          disabled={noMesAtual}
          aria-label="Próximo mês"
        >
          <ChevronRight className="size-4" />
        </Button>
      </div>

      {consumo.isError ? (
        <EmptyState title="Não foi possível carregar os orçamentos" />
      ) : consumo.isLoading ? (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
      ) : (
        <div className="space-y-8">
          {visiveis.length > 0 ? null : mesEhPassado ? (
            <EmptyState
              icon={PiggyBank}
              title="Nenhum orçamento neste mês"
              description="Meses passados não recebem orçamento automaticamente. Aplique o orçamento padrão a este mês, ou configure um orçamento específico só pra ele."
            >
              <div className="flex flex-wrap justify-center gap-2">
                <AplicarPadraoBotao ano={ano} mes={mes} />
                <EditarMesDialog
                  itens={itens}
                  ano={ano}
                  mes={mes}
                  trigger={
                    <Button variant="outline">
                      <Settings2 className="size-4" /> Configurar orçamento do
                      mês
                    </Button>
                  }
                />
              </div>
            </EmptyState>
          ) : (
            <EmptyState
              icon={PiggyBank}
              title="Nenhum orçamento neste mês"
              description="Defina um orçamento padrão pra que ele passe a valer todo mês, a partir de agora."
            >
              <ConfigurarOrcamentoPadraoDialog />
            </EmptyState>
          )}
          {/* Sem linha visível ainda pode haver gasto/receita fora do orçamento: cada aba
              mostra ao menos o "Não planejado". Investimentos (aportes − resgates) ficam
              fora de Despesas e Receitas. */}
          <Tabs defaultValue="despesa">
            <TabsList variant="line" className="w-full justify-start border-b">
              {TIPOS.map((t) => (
                <TabsTrigger key={t} value={t}>
                  {ROTULOS[t].aba}
                </TabsTrigger>
              ))}
            </TabsList>
            {TIPOS.map((t) => (
              <TabsContent key={t} value={t} className="mt-4">
                <SecaoOrcamento
                  tipo={t}
                  itens={visiveis.filter((i) => i.tipo === t)}
                  naoPlanejado={naoPlanejado[t]}
                  {...secao}
                />
              </TabsContent>
            ))}
          </Tabs>
          {visiveis.length === 0 ? null : (
            <ConfigurarOrcamentoPadraoDialog
              trigger={
                <Button variant="outline" className="w-full sm:hidden">
                  <Settings2 className="size-4" /> Configurar orçamento padrão
                </Button>
              }
            />
          )}
        </div>
      )}
    </div>
  )
}

/** Aplica o orçamento padrão a um mês específico sob pedido (a materialização automática só
 *  cobre o mês corrente) — pro caso de um mês passado sem nada configurado. */
function AplicarPadraoBotao({ ano, mes }: { ano: number; mes: number }) {
  const materializar = useMaterializarMes()
  return (
    <Button
      onClick={() =>
        materializar.mutate(
          { ano, mes },
          {
            onSuccess: () =>
              toast.success("Orçamento padrão aplicado a este mês."),
            onError: (err) => toast.error(err.message),
          }
        )
      }
      disabled={materializar.isPending}
    >
      <Wand2 className="size-4" /> Adicionar orçamento padrão
    </Button>
  )
}

/** Linha da Visão Geral — uma categoria orçada ou o "Não planejado" (`categoriaId: null`, sem
 *  limite: orçado/restante "—" e % sempre 100). */
type LinhaVisao = {
  key: string
  categoriaId: string | null
  nome: string
  icone: LucideIcon
  limite: number | null
  realizado: number
  percentual: number
  cor: string
}

function SecaoOrcamento({
  tipo,
  itens,
  naoPlanejado,
  ano,
  mes,
  rotuloMes,
  alvo,
  onAlvo,
}: {
  tipo: TipoOrcamento
  itens: OrcamentoConsumoItem[]
  naoPlanejado: number
  ano: number
  mes: number
  rotuloMes: string
  alvo: AlvoDrilldown | null
  onAlvo: (alvo: AlvoDrilldown | null) => void
}) {
  const nomes = useMapaCategorias()
  const iconeCategoria = useIconeCategoria()
  const grade = useRef<HTMLDivElement>(null)
  const largo = useLargo(grade, 880)
  if (itens.length === 0 && naoPlanejado === 0)
    return (
      <p className="py-6 text-center text-sm text-muted-foreground">
        Nada em {ROTULOS[tipo].aba.toLowerCase()} neste mês.
      </p>
    )

  const despesa = tipo === "despesa"
  const linhas: LinhaVisao[] = itens.map((item) => ({
    key: String(item.orcamento_mensal_id),
    categoriaId: item.categoria_id,
    nome: nomes.get(item.categoria_id) ?? item.categoria_id,
    icone: iconeCategoria(item.categoria_id),
    limite: item.limite_centavos,
    realizado: item.realizado_centavos,
    percentual: item.percentual,
    cor: despesa ? corAlerta(item.alerta_atingido) : "bg-primary",
  }))
  // Investimento líquido pode ser negativo (resgatou mais do que aportou).
  if (naoPlanejado !== 0)
    linhas.push({
      key: "nao-planejado",
      categoriaId: null,
      nome: "Não planejado",
      icone: CircleDashed,
      limite: null,
      realizado: naoPlanejado,
      percentual: 100, // sem orçado: por definição tudo está "fora" do planejado
      cor: "bg-muted-foreground",
    })

  const totalOrcado = itens.reduce((acc, i) => acc + i.limite_centavos, 0)
  // O não planejado entra no realizado: o resumo reflete tudo o que saiu/entrou no mês.
  const totalRealizado = linhas.reduce((acc, l) => acc + l.realizado, 0)
  const restanteTotal = totalOrcado - totalRealizado
  const percentualTotal =
    totalOrcado > 0
      ? Math.round((totalRealizado / totalOrcado) * 100)
      : totalRealizado > 0
        ? 100
        : 0

  const abertaKey =
    alvo?.tipo === tipo
      ? (linhas.find((l) => l.categoriaId === alvo.categoriaId)?.key ?? null)
      : null
  const aberta = linhas.find((l) => l.key === abertaKey) ?? null
  function alternar(linha: LinhaVisao) {
    onAlvo(
      linha.key === abertaKey ? null : { tipo, categoriaId: linha.categoriaId }
    )
  }

  return (
    <section className="space-y-3">
      <h2 className="sr-only">{ROTULOS[tipo].aba}</h2>

      <ResumoSecao
        tipo={tipo}
        totalOrcado={totalOrcado}
        totalRealizado={totalRealizado}
        restanteTotal={restanteTotal}
        percentualTotal={percentualTotal}
      />

      {/* Largo: categorias à esquerda, transações da escolhida à direita. Estreito: a categoria
          abre as transações logo abaixo dela (sanfona: abrir outra fecha a anterior). A decisão
          é pela largura DISPONÍVEL (chat aberto estreita a página), não pela da janela. */}
      <div
        ref={grade}
        className={cn(
          largo &&
            "grid grid-cols-[minmax(18rem,26rem)_minmax(0,1fr)] items-start gap-4"
        )}
      >
        <ListaCategorias
          linhas={linhas}
          abertaKey={abertaKey}
          onAlternar={alternar}
          detalhe={
            largo
              ? undefined
              : (linha) => (
                  <PainelTransacoes
                    ano={ano}
                    mes={mes}
                    alvo={{ tipo, categoriaId: linha.categoriaId }}
                    titulo={`${linha.nome} · ${rotuloMes}`}
                    embutido
                  />
                )
          }
        />
        {largo ? (
          // key = categoria: trocar de categoria remonta o painel e toca a entrada (fade + leve
          // subida) — a troca de conteúdo lê como transição, não como pulo.
          <div
            key={abertaKey ?? "vazio"}
            className="sticky top-4 animate-[entrada-pagina_260ms_var(--ease-out)_both] motion-reduce:animate-[entrada-fade_150ms_ease_both]"
          >
            {aberta && alvo ? (
              <PainelTransacoes
                ano={ano}
                mes={mes}
                alvo={alvo}
                titulo={`${aberta.nome} · ${rotuloMes}`}
                onFechar={() => onAlvo(null)}
              />
            ) : (
              <div className="flex min-h-64 flex-col items-center justify-center gap-2 rounded-2xl border border-dashed p-8 text-center">
                <ListFilter
                  className="size-5 text-muted-foreground"
                  aria-hidden
                />
                <p className="text-sm font-medium">Escolha uma categoria</p>
                <p className="max-w-xs text-sm text-muted-foreground">
                  As transações dela no mês aparecem aqui.
                </p>
              </div>
            )}
          </div>
        ) : null}
      </div>
    </section>
  )
}

function ResumoSecao({
  tipo,
  totalOrcado,
  totalRealizado,
  restanteTotal,
  percentualTotal,
}: {
  tipo: TipoOrcamento
  totalOrcado: number
  totalRealizado: number
  restanteTotal: number
  percentualTotal: number
}) {
  const despesa = tipo === "despesa"
  const r = ROTULOS[tipo]
  const excedido = despesa && restanteTotal < 0
  const pct = Math.max(0, percentualTotal)
  return (
    // Herói = o que resta (a pergunta do mês), com orçado e realizado na própria linha do herói.
    <CardDestaque
      // Rótulo muda ao estourar: o valor sai sem "-", então a cor não pode ser o único sinal.
      titulo={excedido ? "Excedido no mês" : r.restanteTotal}
      // Nas metas (receita/investimento), passar da meta zera o restante — o excedente não
      // é "o que falta".
      centavos={despesa ? Math.abs(restanteTotal) : Math.max(restanteTotal, 0)}
      mascote={despesa ? (pct >= 100 ? "scared" : "money") : "goal"}
      estatisticas={[
        {
          rotulo: r.orcadoTotal,
          valor: <Valor centavos={totalOrcado} neutro />,
        },
        {
          rotulo: r.realizadoTotal,
          valor: <Valor centavos={totalRealizado} neutro />,
        },
      ]}
    >
      <div className="max-w-xl space-y-2">
        <div
          role="img"
          aria-label={`${pct}% ${r.anel}`}
          className="h-2.5 w-full overflow-hidden rounded-full bg-muted"
        >
          <div
            className={cn(
              "h-full origin-left animate-[barra-cresce_800ms_var(--ease-out)_both] rounded-full motion-reduce:animate-none",
              excedido
                ? "bg-negative"
                : pct >= 75 && despesa
                  ? "bg-warning"
                  : "bg-success"
            )}
            style={{ width: `${Math.min(pct, 100)}%` }}
          />
        </div>
        <p className="text-sm font-semibold text-muted-foreground tabular-nums">
          {pct}% {r.anel}
        </p>
      </div>
    </CardDestaque>
  )
}

/** Largura do elemento ≥ `min` (px), acompanhando redimensionamentos. */
function useLargo(ref: RefObject<HTMLElement | null>, min: number) {
  const [largo, setLargo] = useState(false)
  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    const ro = new ResizeObserver(([e]) => setLargo(e.contentRect.width >= min))
    ro.observe(el)
    return () => ro.disconnect()
  }, [ref, min])
  return largo
}

function ListaCategorias({
  linhas,
  abertaKey,
  onAlternar,
  detalhe,
}: {
  linhas: LinhaVisao[]
  abertaKey: string | null
  onAlternar: (linha: LinhaVisao) => void
  /** Transações de uma categoria, embutidas logo abaixo dela (modo sanfona); sem ela, nada abre
   *  na lista (o painel mora ao lado). */
  detalhe?: (linha: LinhaVisao) => ReactNode
}) {
  return (
    <div className="space-y-0.5 rounded-2xl superficie p-2">
      {linhas.map((linha) => {
        const aberta = linha.key === abertaKey
        return (
          <ItemCategoria
            key={linha.key}
            linha={linha}
            aberta={aberta}
            onAlternar={onAlternar}
            detalhe={detalhe}
          />
        )
      })}
    </div>
  )
}

function ItemCategoria({
  linha,
  aberta,
  onAlternar,
  detalhe,
}: {
  linha: LinhaVisao
  aberta: boolean
  onAlternar: (linha: LinhaVisao) => void
  detalhe?: (linha: LinhaVisao) => ReactNode
}) {
  // Conteúdo continua montado enquanto fecha (a altura anima até 0) e sai no fim da transição.
  const [montado, setMontado] = useState(aberta)
  if (aberta && !montado) setMontado(true)

  function alternar(e: MouseEvent<HTMLButtonElement>) {
    // A linha tocada fica parada na tela: se outra categoria ACIMA fecha, a página subiria junto —
    // compensamos a rolagem a cada quadro enquanto as alturas animam.
    const el = e.currentTarget
    const y0 = el.getBoundingClientRect().top
    const fim = performance.now() + 400
    const fixar = () => {
      const d = el.getBoundingClientRect().top - y0
      if (Math.abs(d) > 0.5) window.scrollBy(0, d)
      if (performance.now() < fim) requestAnimationFrame(fixar)
    }
    onAlternar(linha)
    requestAnimationFrame(fixar)
  }

  return (
    <div
      className={cn(
        "space-y-1.5 rounded-xl p-3 transition-colors",
        aberta ? "bg-muted/60" : "hover:bg-muted/40"
      )}
    >
      <button
        type="button"
        onClick={alternar}
        aria-expanded={detalhe ? aberta : undefined}
        aria-pressed={detalhe ? undefined : aberta}
        className="flex w-full items-center gap-3 rounded-sm text-left outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        {createElement(linha.icone, {
          className: "size-4 shrink-0 text-muted-foreground",
          "aria-hidden": true,
        })}
        <span className="min-w-0 flex-1 space-y-1.5">
          <span className="flex items-center justify-between gap-2">
            <span className="truncate text-sm font-medium">{linha.nome}</span>
            <span className="shrink-0 text-xs text-muted-foreground tabular-nums">
              {linha.percentual}%
            </span>
          </span>
          <RealizadoDeLimite linha={linha} />
        </span>
      </button>
      {/* Fora do botão: <div role=progressbar> dentro de <button> é HTML inválido. */}
      <div className="pl-7">
        <Progress
          value={Math.min(linha.percentual, 100)}
          indicatorClassName={linha.cor}
        />
      </div>
      {detalhe ? (
        // Sanfona: grid 0fr → 1fr anima a altura até a do conteúdo (sem medir em JS); o conteúdo
        // acompanha com opacidade. mt-0: fechada, não deixa o espaçamento do space-y sobrando.
        <div
          className={cn(
            "mt-0! grid transition-[grid-template-rows] duration-300 ease-(--ease-out) motion-reduce:transition-none",
            aberta ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
          )}
          onTransitionEnd={(e) => {
            if (e.target === e.currentTarget && !aberta) setMontado(false)
          }}
        >
          <div
            className={cn(
              "min-h-0 overflow-hidden transition-opacity duration-300 ease-(--ease-out) motion-reduce:transition-none",
              aberta ? "opacity-100" : "opacity-0"
            )}
            inert={!aberta || undefined}
          >
            {montado ? detalhe(linha) : null}
          </div>
        </div>
      ) : null}
    </div>
  )
}

function RealizadoDeLimite({ linha }: { linha: LinhaVisao }) {
  return (
    <span className="block text-xs text-muted-foreground">
      <Valor
        centavos={linha.realizado}
        neutro
        className="text-xs font-normal"
      />{" "}
      {linha.limite === null ? (
        "fora do orçamento"
      ) : (
        <>
          de{" "}
          <Valor
            centavos={linha.limite}
            neutro
            className="text-xs font-normal"
          />
        </>
      )}
    </span>
  )
}

function PainelTransacoes({
  ano,
  mes,
  alvo,
  titulo,
  onFechar,
  embutido = false,
}: {
  ano: number
  mes: number
  alvo: AlvoDrilldown
  titulo: string
  /** Sem ele, não há botão de fechar (na sanfona, fecha-se tocando a categoria de novo). */
  onFechar?: () => void
  /** Dentro da categoria aberta (sanfona): sem superfície própria nem título. */
  embutido?: boolean
}) {
  const transacoes = useTransacoesDoOrcamento(ano, mes, alvo)
  const ref = useRef<HTMLElement>(null)
  // Traz o painel pra vista ao abrir/trocar de linha — numa tabela longa ele nasceria fora da tela.
  // Na sanfona não: a página fica parada e só a categoria expande.
  useEffect(() => {
    if (!embutido) ref.current?.scrollIntoView({ block: "nearest" })
  }, [alvo.tipo, alvo.categoriaId, embutido])

  return (
    <section
      ref={ref}
      aria-label={`Transações de ${titulo}`}
      className={cn(
        embutido ? "-mx-1 pt-2" : "space-y-3 rounded-2xl superficie p-3 sm:p-4"
      )}
    >
      {embutido ? null : (
        <div className="flex items-center justify-between gap-2">
          <h3 className="text-sm font-semibold">
            <span className="text-muted-foreground">Transações · </span>
            {titulo}
          </h3>
          {onFechar ? (
            <Button
              variant="ghost"
              size="icon"
              onClick={onFechar}
              aria-label="Fechar transações"
            >
              <X className="size-4" />
            </Button>
          ) : null}
        </div>
      )}
      {transacoes.isError ? (
        <EmptyState title="Não foi possível carregar as transações" />
      ) : transacoes.isLoading ? (
        <Skeleton className="h-24 w-full" />
      ) : !transacoes.data?.length ? (
        <EmptyState title="Nenhuma transação nesta categoria no mês" />
      ) : (
        <TransacoesTabela
          items={transacoes.data}
          semMoldura
          // Categoria única na lista → coluna redundante (o "não planejado" mistura várias).
          ocultarCategoria={alvo.categoriaId != null}
        />
      )}
    </section>
  )
}
