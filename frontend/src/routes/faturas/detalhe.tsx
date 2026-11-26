import { ArrowLeft, Info, Receipt } from "lucide-react"
import { Link, useParams } from "react-router"

import { CartaoArt } from "@/components/contas/cartao-art"
import { EmptyState } from "@/components/common/empty-state"
import { CardDestaque } from "@/components/common/kpi"
import { PageHeader } from "@/components/common/page-header"
import { Selo } from "@/components/common/selo"
import { Valor } from "@/components/common/valor"
import { TransacoesTabela } from "@/components/transacoes/transacoes-tabela"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { useConta } from "@/lib/api/contas"
import { useFatura } from "@/lib/api/faturas"
import { instituicaoEfetiva, useInstituicoes } from "@/lib/api/instituicoes"
import { useTransacoes } from "@/lib/api/transacoes"
import { formatDate, formatMesAno, statusFatura } from "@/lib/format"

export function FaturaDetalhePage() {
  const { faturaId } = useParams()
  const id = Number(faturaId)
  const fatura = useFatura(id)
  const transacoes = useTransacoes({ fatura_id: id, limit: 200 })
  // O cartão da fatura vira a arte do herói (a mesma do card em Contas e cartões).
  const cartao = useConta(fatura.data?.cartao_id ?? 0)
  const instituicoes = useInstituicoes()

  if (fatura.isError) return <EmptyState title="Fatura não encontrada" />
  if (fatura.isLoading || !fatura.data)
    return <Skeleton className="h-64 w-full" />

  const f = fatura.data
  const st = statusFatura(f.due_date)
  const itens = transacoes.data?.items ?? []
  const c = cartao.data
  const nomeCartao = c ? (c.marketing_name ?? c.nome ?? "Cartão") : ""
  const logoUrl = c
    ? instituicaoEfetiva(
        c,
        new Map((instituicoes.data ?? []).map((i) => [i.id, i]))
      )?.logo_url
    : undefined

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
        titulo="Total da fatura"
        centavos={f.total_amount_centavos}
        arte={
          c ? (
            <CartaoArt conta={c} nome={nomeCartao} logoUrl={logoUrl} />
          ) : undefined
        }
        estatisticas={[
          ...(f.minimum_payment_centavos
            ? [
                {
                  rotulo: "Pagamento mínimo",
                  valor: <Valor centavos={f.minimum_payment_centavos} neutro />,
                },
              ]
            : []),
          ...(transacoes.isLoading
            ? []
            : [
                {
                  rotulo: "Compras",
                  valor: String(transacoes.data?.total ?? itens.length),
                },
              ]),
        ]}
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
