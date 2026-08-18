import { ArrowLeft, ArrowRightLeft, CreditCard, RefreshCw } from "lucide-react"
import { useState } from "react"
import { Link, useParams } from "react-router"

import { AvatarBanco } from "@/components/contas/avatar-banco"
import { CartaoFlip } from "@/components/contas/cartao-flip"
import { GraficoFaturas } from "@/components/contas/grafico-faturas"
import { EmptyState } from "@/components/common/empty-state"
import { Valor } from "@/components/common/valor"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useConta, type ContaDetalhe } from "@/lib/api/contas"
import { instituicaoEfetiva, useInstituicoes } from "@/lib/api/instituicoes"
import { formatBRL, formatDate, mascarar } from "@/lib/format"

export function ContaDetalhePage() {
  const { contaId } = useParams()
  const id = Number(contaId)
  const { data, isLoading, isError } = useConta(id)
  const instituicoes = useInstituicoes()

  if (isError) return <EmptyState title="Conta não encontrada" />
  if (isLoading || !data) return <Skeleton className="h-64 w-full" />

  const porId = new Map((instituicoes.data ?? []).map((i) => [i.id, i]))
  const efetiva = instituicaoEfetiva(data, porId)
  const nome = data.marketing_name ?? data.nome ?? "Conta"

  return (
    <div className="space-y-5">
      <Button asChild variant="ghost" size="sm" className="-ml-2">
        <Link to="/contas">
          <ArrowLeft className="size-4" aria-hidden /> Contas
        </Link>
      </Button>

      <header>
        <h1 className="text-xl font-semibold">
          {data.marketing_name ?? data.nome ?? "Conta"}
        </h1>
        <p className="text-sm text-muted-foreground">
          {data.type === "CREDIT" ? "Cartão de crédito" : "Conta"} ·{" "}
          {mascarar(data.numero)}
        </p>
        {data.type !== "CREDIT" ? (
          <p className="mt-2 text-2xl">
            <Valor centavos={data.saldo_centavos} />
          </p>
        ) : null}
        {data.objetivo_id ? (
          <p className="mt-1 text-xs text-muted-foreground">
            Vinculada a um objetivo.
          </p>
        ) : null}
      </header>

      <div className="flex items-center gap-3 rounded-lg border p-3">
        <AvatarBanco nome={efetiva?.nome ?? "?"} logoUrl={efetiva?.logo_url} />
        <div className="min-w-0 flex-1">
          <p className="text-xs text-muted-foreground">Instituição</p>
          <p className="truncate font-medium">{efetiva?.nome ?? "—"}</p>
        </div>
      </div>

      {data.conta_bancaria ? <DetalheBanco conta={data} /> : null}
      {data.cartao ? (
        <DetalheCartao conta={data} nome={nome} logoUrl={efetiva?.logo_url} />
      ) : null}

      <div className="flex flex-col gap-2 sm:flex-row">
        <Button asChild variant="outline">
          <Link to={`/transacoes?conta_id=${id}`}>
            <ArrowRightLeft className="size-4" aria-hidden /> Ver todas as
            transações
          </Link>
        </Button>
        {data.cartao ? (
          <Button asChild variant="outline">
            <Link to={`/faturas?cartao_id=${id}`}>
              <CreditCard className="size-4" aria-hidden /> Ver faturas
            </Link>
          </Button>
        ) : null}
      </div>

      {data.cartao ? <GraficoFaturas contaId={id} /> : null}
    </div>
  )
}

function DetalheBanco({ conta }: { conta: ContaDetalhe }) {
  const b = conta.conta_bancaria!
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Detalhes da conta</CardTitle>
      </CardHeader>
      <CardContent className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
        <Item
          rotulo="Saldo de fechamento"
          centavos={b.closing_balance_centavos}
        />
        <Item
          rotulo="Investido automaticamente"
          centavos={b.automatically_invested_balance_centavos}
        />
        <Item
          rotulo="Limite de cheque especial"
          centavos={b.overdraft_contracted_limit_centavos}
        />
        {conta.saldos_reservados.length > 0 ? (
          <div className="col-span-full">
            <p className="mb-1 text-xs text-muted-foreground">Caixinhas</p>
            <ul className="space-y-1">
              {conta.saldos_reservados.map((r) => (
                <li key={r.id} className="flex justify-between">
                  <span>{r.nome ?? "Reserva"}</span>
                  <Valor centavos={r.valor_centavos ?? 0} />
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}

function DetalheCartao({
  conta,
  nome,
  logoUrl,
}: {
  conta: ContaDetalhe
  nome: string
  logoUrl?: string | null
}) {
  const c = conta.cartao!
  const [virado, setVirado] = useState(false)
  const virar = () => setVirado((v) => !v)

  return (
    <div className="grid gap-x-5 gap-y-3 lg:grid-cols-[minmax(0,20rem)_1fr] lg:grid-rows-[auto_auto]">
      {/* Cartão e "Virar" na coluna esquerda (linhas 1 e 2); o painel ocupa só a linha do
          cartão (col-start-2 row-start-1), casando a altura com o cartão — não com o botão. */}
      <div className="lg:col-start-1 lg:row-start-1">
        <CartaoFlip
          conta={conta}
          nome={nome}
          logoUrl={logoUrl}
          virado={virado}
          onVirar={virar}
        />
      </div>

      <div className="flex justify-center lg:col-start-1 lg:row-start-2">
        <Button variant="ghost" size="sm" onClick={virar} aria-pressed={virado}>
          <RefreshCw className="size-4" aria-hidden /> Virar cartão
        </Button>
      </div>

      <dl className="grid grid-cols-2 gap-x-6 gap-y-5 rounded-2xl border bg-card p-5 sm:grid-cols-3 sm:p-6 lg:col-start-2 lg:row-start-1 lg:content-center">
        <Metrica rotulo="Limite total" centavos={c.credit_limit_centavos} />
        <Metrica
          rotulo="Limite disponível"
          centavos={c.available_credit_limit_centavos}
        />
        <DataItem rotulo="Vencimento" data={c.balance_due_date} />
        <Metrica
          rotulo="Pagamento mínimo"
          centavos={c.minimum_payment_centavos}
        />
        <DataItem rotulo="Fechamento" data={c.balance_close_date} />
      </dl>
    </div>
  )
}

/** Valor monetário do painel do cartão — realçado no accent (identidade da referência). */
function Metrica({
  rotulo,
  centavos,
}: {
  rotulo: string
  centavos: number | null | undefined
}) {
  if (centavos === null || centavos === undefined) return null
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{rotulo}</dt>
      <dd className="font-semibold text-accent-ink tabular-nums">
        {formatBRL(centavos)}
      </dd>
    </div>
  )
}

function DataItem({
  rotulo,
  data,
}: {
  rotulo: string
  data: string | null | undefined
}) {
  if (!data) return null
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{rotulo}</dt>
      <dd className="font-medium">{formatDate(data)}</dd>
    </div>
  )
}

function Item({
  rotulo,
  centavos,
}: {
  rotulo: string
  centavos: number | null | undefined
}) {
  if (centavos === null || centavos === undefined) return null
  return (
    <div>
      <p className="text-xs text-muted-foreground">{rotulo}</p>
      <Valor centavos={centavos} />
    </div>
  )
}
