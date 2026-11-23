import { TransacoesTabela } from "@/components/transacoes/transacoes-tabela"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Skeleton } from "@/components/ui/skeleton"
import { useTransacoes } from "@/lib/api/transacoes"
import { formatDate } from "@/lib/format"

const LIMITE = 200 // teto da API de listagem

/**
 * Transações de uma categoria no período (clique nos gráficos de categoria do dashboard). Mesmo
 * recorte do gráfico: saídas (DEBIT), sem transferências, categoria efetiva exata, com as parcelas
 * de divisão — a soma bate com a fatia.
 */
export function TransacoesCategoriaDialog({
  categoria,
  inicio,
  fim,
  onFechar,
}: {
  categoria: { id: string; nome: string } | null
  inicio: string
  fim: string
  onFechar: () => void
}) {
  const lista = useTransacoes(
    {
      categoria_id: categoria?.id,
      inicio,
      fim,
      tipo: "DEBIT",
      eh_transferencia: false,
      limit: LIMITE,
    },
    { enabled: categoria != null }
  )
  const itens = lista.data?.items ?? []
  const total = lista.data?.total ?? 0
  return (
    <Dialog open={categoria != null} onOpenChange={(v) => v || onFechar()}>
      {/* Corpo rolável, cabeçalho fixo (mobile: cabe na tela inteira). */}
      <DialogContent className="flex max-h-[calc(100dvh-2rem)] flex-col gap-0 p-0 sm:max-w-5xl">
        <DialogHeader className="shrink-0 border-b p-6 pb-4">
          <DialogTitle>{categoria?.nome}</DialogTitle>
          <DialogDescription>
            Despesas de {formatDate(`${inicio}T12:00:00`)} a{" "}
            {formatDate(`${fim}T12:00:00`)}
            {lista.data
              ? ` · ${total} ${total === 1 ? "transação" : "transações"}`
              : ""}
          </DialogDescription>
        </DialogHeader>
        <div className="min-h-0 flex-1 overflow-y-auto p-6 pt-4">
          {lista.isLoading ? (
            <Skeleton className="h-64 w-full" />
          ) : lista.isError ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              Não foi possível carregar as transações.
            </p>
          ) : itens.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              Nenhuma transação nesta categoria no período.
            </p>
          ) : (
            <>
              <TransacoesTabela items={itens} ocultarCategoria />
              {total > itens.length ? (
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
