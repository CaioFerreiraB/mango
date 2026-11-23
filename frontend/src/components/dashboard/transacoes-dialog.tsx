import { TransacoesTabela } from "@/components/transacoes/transacoes-tabela"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Skeleton } from "@/components/ui/skeleton"
import { useTransacoesDaAnalise, type FiltroAnalise } from "@/lib/api/dashboard"
import {
  useTransacoesDoOrcamento,
  type AlvoDrilldown,
} from "@/lib/api/orcamentos"
import type { ItemListagem } from "@/lib/api/transacoes"
import { formatDate } from "@/lib/format"

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
  onFechar,
}: {
  filtro: FiltroAnalise | null
  inicio: string
  fim: string
  onFechar: () => void
}) {
  const lista = useTransacoesDaAnalise(filtro, { inicio, fim })
  return (
    <ListaDialog
      aberto={filtro != null}
      titulo={filtro?.titulo ?? ""}
      descricao={`${filtro ? NATUREZA[filtro.natureza] : ""} de ${dia(inicio)} a ${dia(fim)}`}
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

/** Transações de uma linha do orçamento no mês (`/orcamentos/consumo/transacoes`). */
export function TransacoesOrcamentoDialog({
  ano,
  mes,
  alvo,
  titulo,
  onFechar,
}: {
  ano: number
  mes: number
  alvo: AlvoDrilldown | null
  titulo: string
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
      onFechar={onFechar}
    />
  )
}
