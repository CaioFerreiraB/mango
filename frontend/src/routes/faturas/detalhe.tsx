import { ArrowLeft, Info, Receipt } from "lucide-react"
import { Link, useParams } from "react-router"

import { EmptyState } from "@/components/common/empty-state"
import { CardDestaque } from "@/components/common/kpi"
import { PageHeader } from "@/components/common/page-header"
import { Selo } from "@/components/common/selo"
import { Valor } from "@/components/common/valor"
import { TransacoesTabela } from "@/components/transacoes/transacoes-tabela"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { useFatura } from "@/lib/api/faturas"
import { useTransacoes } from "@/lib/api/transacoes"
import { formatDate, formatMesAno, statusFatura } from "@/lib/format"

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
    <div className="space-y-6">
      {/* Desktop já tem o breadcrumb; no mobile a topbar só mostra a página atual. */}
      <Button asChild variant="ghost" size="sm" className="-ml-2 md:hidden">
        <Link to="/faturas">
          <ArrowLeft className="size-4" aria-hidden /> Faturas
        </Link>
      </Button>

      <PageHeader
        titulo={`Fatura de ${formatMesAno(f.due_date)}`}
        descricao={
          <span className="inline-flex flex-wrap items-center gap-2">
            Vence {formatDate(f.due_date)}
            <Selo tom={st.aberta ? "neutro" : "apagado"}>{st.rotulo}</Selo>
          </span>
        }
      />

      <CardDestaque
        className="sm:max-w-md"
        titulo="Total da fatura"
        centavos={f.total_amount_centavos}
        rodape={
          f.minimum_payment_centavos ? (
            <>
              Pagamento mínimo{" "}
              <Valor centavos={f.minimum_payment_centavos} neutro />
            </>
          ) : undefined
        }
      />

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
          <EmptyState
            icon={Receipt}
            title="Nenhuma compra vinculada"
            description="As compras aparecem aqui quando o banco as associa a esta fatura no próximo sync."
            className="py-10"
          />
        ) : (
          <TransacoesTabela items={itens} ocultarLinkFatura />
        )}
      </section>
    </div>
  )
}
