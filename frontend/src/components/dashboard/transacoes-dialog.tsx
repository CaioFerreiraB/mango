import type { ReactNode } from "react"

import { TransacoesTabela } from "@/components/transacoes/transacoes-tabela"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Progress } from "@/components/ui/progress"
import { Skeleton } from "@/components/ui/skeleton"
import {
  useTransacoesDaAnalise,
  type FiltroAnalise,
  type Visao,
} from "@/lib/api/dashboard"
import {
  useTransacoesDoOrcamento,
  type AlvoDrilldown,
} from "@/lib/api/orcamentos"
import type { ItemListagem } from "@/lib/api/transacoes"
import { formatBRL, formatDate } from "@/lib/format"
import { cn } from "@/lib/utils"

const NATUREZA = { receita: "Receitas", despesa: "Despesas" } as const

/** Casca comum: cabeçalho fixo, corpo rolável (mobile cabe na tela), estados de carga/erro/vazio. */
function ListaDialog({
  aberto,
  titulo,
  descricao,
  itens,
  total,
  carregando,
  erro,
  ocultarCategoria,
  resumo,
  onFechar,
}: {
  aberto: boolean
  titulo: string
  descricao: string
  itens: ItemListagem[]
  total: number | undefined
  carregando: boolean
  erro: boolean
  ocultarCategoria: boolean
  /** Faixa fixa entre o cabeçalho e a lista (não rola junto). */
  resumo?: ReactNode
  onFechar: () => void
}) {
  return (
    <Dialog open={aberto} onOpenChange={(v) => v || onFechar()}>
      <DialogContent className="flex max-h-[calc(100dvh-2rem)] flex-col gap-0 p-0 sm:max-w-5xl">
        <DialogHeader className="shrink-0 border-b p-6 pb-4">
          <DialogTitle>{titulo}</DialogTitle>
          <DialogDescription>
            {descricao}
            {total != null
              ? ` · ${total} ${total === 1 ? "transação" : "transações"}`
              : ""}
          </DialogDescription>
        </DialogHeader>
        {resumo}
        <div className="min-h-0 flex-1 overflow-y-auto p-6 pt-4">
          {carregando ? (
            <Skeleton className="h-64 w-full" />
          ) : erro ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              Não foi possível carregar as transações.
            </p>
          ) : itens.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              Nenhuma transação no período.
            </p>
          ) : (
            <>
              <TransacoesTabela
                items={itens}
                ocultarCategoria={ocultarCategoria}
                parteDoUsuario
              />
              {total != null && total > itens.length ? (
                <p className="pt-3 text-center text-xs text-muted-foreground">
                  Mostrando as {itens.length} mais recentes de {total}.
                </p>
              ) : null}
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}

const dia = (iso: string) => formatDate(`${iso}T12:00:00`)

/**
 * Transações de um pedaço de gráfico das abas (categoria, fonte/estabelecimento, meio, conta).
 * Mesmo recorte do servidor (`/dashboard/analise/transacoes`): a soma bate com o gráfico.
 */
export function TransacoesAnaliseDialog({
  filtro,
  inicio,
  fim,
  visao,
  onFechar,
}: {
  filtro: FiltroAnalise | null
  inicio: string
  fim: string
  visao: Visao
  onFechar: () => void
}) {
  const lista = useTransacoesDaAnalise(filtro, { inicio, fim }, visao)
  return (
    <ListaDialog
      aberto={filtro != null}
      titulo={filtro?.titulo ?? ""}
      descricao={`${filtro?.natureza ? NATUREZA[filtro.natureza] : "Lançamentos"} de ${dia(inicio)} a ${dia(fim)}`}
      itens={lista.data?.items ?? []}
      total={lista.data?.total}
      carregando={lista.isLoading}
      erro={lista.isError}
      // Categoria única na lista → coluna redundante (e a tabela cabe no diálogo).
      ocultarCategoria={filtro?.categoria_id != null}
      onFechar={onFechar}
    />
  )
}

export type ConsumoLinha = {
  realizado: number
  limite: number
  percentual: number
}

/** Gasto × orçamento da linha: o gasto é o protagonista, o limite vem ao lado; a barra e o status
 *  em palavras repetem a leitura (cor nunca sozinha — "Passou" diz o estouro). */
function ResumoConsumo({ realizado, limite, percentual }: ConsumoLinha) {
  const sobra = limite - realizado
  const estourou = sobra < 0
  return (
    <section
      aria-label="Gasto e orçamento"
      className="shrink-0 space-y-3 border-b bg-muted/40 px-6 py-4"
    >
      <dl className="flex flex-wrap items-end gap-x-10 gap-y-3">
        <div>
          <dt className="text-sm text-muted-foreground">Gasto</dt>
          <dd className="text-3xl font-semibold tracking-tight tabular-nums">
            {formatBRL(realizado)}
          </dd>
        </div>
        <div>
          <dt className="text-sm text-muted-foreground">Orçamento</dt>
          <dd className="text-xl font-semibold tabular-nums">
            {formatBRL(limite)}
          </dd>
        </div>
      </dl>
      <Progress
        value={Math.min(percentual, 100)}
        className="bg-muted"
        indicatorClassName={estourou ? "bg-negative" : "bg-positive"}
      />
      <p className="flex flex-wrap justify-between gap-x-4 text-sm">
        <span className={cn("font-medium", estourou && "text-negative-ink")}>
          {estourou
            ? `Passou ${formatBRL(-sobra)} do limite`
            : `Restam ${formatBRL(sobra)}`}
        </span>
        <span className="text-muted-foreground tabular-nums">
          {percentual}% usado
        </span>
      </p>
    </section>
  )
}

/** Transações de uma linha do orçamento no mês (`/orcamentos/consumo/transacoes`). */
export function TransacoesOrcamentoDialog({
  ano,
  mes,
  alvo,
  titulo,
  consumo,
  onFechar,
}: {
  ano: number
  mes: number
  alvo: AlvoDrilldown | null
  titulo: string
  consumo?: ConsumoLinha
  onFechar: () => void
}) {
  const lista = useTransacoesDoOrcamento(ano, mes, alvo)
  const nomeMes = new Date(ano, mes - 1, 1).toLocaleDateString("pt-BR", {
    month: "long",
    year: "numeric",
  })
  return (
    <ListaDialog
      aberto={alvo != null}
      titulo={titulo}
      descricao={`Orçamento de ${nomeMes} (com subcategorias)`}
      itens={lista.data ?? []}
      total={lista.data?.length}
      carregando={lista.isLoading}
      erro={lista.isError}
      ocultarCategoria={false}
      resumo={consumo ? <ResumoConsumo {...consumo} /> : undefined}
      onFechar={onFechar}
    />
  )
}

/**
 * Lançamentos de um período (dia ou mês do calendário do dashboard): o drill-down da análise sem
 * `natureza`, no recorte da visão — a mesma base dos totais do calendário (na visão caixa entra o
 * pagamento de fatura e saem as compras no cartão).
 */
export function TransacoesPeriodoDialog({
  periodo,
  visao,
  onFechar,
}: {
  periodo: { inicio: string; fim: string; titulo: string } | null
  visao: Visao
  onFechar: () => void
}) {
  const lista = useTransacoesDaAnalise(
    periodo ? { titulo: periodo.titulo } : null,
    { inicio: periodo?.inicio ?? "", fim: periodo?.fim ?? "" },
    visao
  )
  return (
    <ListaDialog
      aberto={periodo != null}
      titulo={periodo?.titulo ?? ""}
      descricao={
        visao === "caixa"
          ? "Visão caixa: só o que mexeu nas contas (pagamento de fatura no lugar das compras no cartão)"
          : "Visão competência: compras no cartão na data da compra, sem transferências"
      }
      itens={lista.data?.items ?? []}
      total={lista.data?.total}
      carregando={lista.isLoading}
      erro={lista.isError}
      ocultarCategoria={false}
      onFechar={onFechar}
    />
  )
}
