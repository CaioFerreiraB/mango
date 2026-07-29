import { ArrowLeft, Info } from "lucide-react"
import { Link, useParams } from "react-router"

import { EmptyState } from "@/components/common/empty-state"
import { Valor } from "@/components/common/valor"
import { TransacoesTabela } from "@/components/transacoes/transacoes-tabela"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { useFatura } from "@/lib/api/faturas"
import { useTransacoes } from "@/lib/api/transacoes"
import { formatDate, statusFatura } from "@/lib/format"

export function FaturaDetalhePage() {
  const { faturaId } = useParams()
  const id = Number(faturaId)
  const fatura = useFatura(id)
  const transacoes = useTransacoes({ fatura_id: id, limit: 200 })

  if (fatura.isError) return <EmptyState title="Fatura não encontrada" />
  if (fatura.isLoading || !fatura.data)
    return <Skeleton className="h-64 w-full" />

  const f = fatura.data
  const st = statusFatura(f.due_date)
  const itens = transacoes.data?.items ?? []

  return (
    <div className="space-y-5">
      <Button asChild variant="ghost" size="sm" className="-ml-2">
        <Link to="/faturas">
          <ArrowLeft className="size-4" aria-hidden /> Faturas
        </Link>
      </Button>

      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Fatura · {st.rotulo}</h1>
          <p className="text-sm text-muted-foreground">
            Vencimento {formatDate(f.due_date)}
          </p>
        </div>
        <div className="text-right">
          <Valor centavos={-f.total_amount_centavos} className="text-2xl" />
          {f.minimum_payment_centavos ? (
            <p className="text-xs text-muted-foreground">
              Pagamento mínimo <Valor centavos={f.minimum_payment_centavos} />
            </p>
          ) : null}
        </div>
      </header>

      <Alert>
        <Info className="size-4" aria-hidden />
        <AlertTitle>Competência × caixa</AlertTitle>
        <AlertDescription>
          As compras abaixo contam no mês em que ocorreram. O pagamento da
          fatura é uma transferência e não é recontabilizado nas saídas.
        </AlertDescription>
      </Alert>

      <section className="space-y-2">
        <h2 className="text-base font-semibold">Compras nesta fatura</h2>
        {transacoes.isLoading ? (
          <Skeleton className="h-64 w-full" />
        ) : itens.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Nenhuma transação vinculada a esta fatura.
          </p>
        ) : (
          <TransacoesTabela items={itens} ocultarLinkFatura />
        )}
      </section>
    </div>
  )
}
