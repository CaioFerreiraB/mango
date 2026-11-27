import { ArrowLeft, ArrowRightLeft, CreditCard, RefreshCw } from "lucide-react"
import { useState, type ReactNode } from "react"
import { Link, useParams } from "react-router"

import { AvatarBanco } from "@/components/contas/avatar-banco"
import { CartaoFlip } from "@/components/contas/cartao-flip"
import { GraficoFaturas } from "@/components/contas/grafico-faturas"
import { EmptyState } from "@/components/common/empty-state"
import { CardDestaque } from "@/components/common/kpi"
import { PageHeader } from "@/components/common/page-header"
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

  // Id inválido na URL (/contas/abc): a consulta fica desligada (useConta só pergunta por id > 0)
  // e o esqueleto ficaria para sempre.
  if (isError || !Number.isInteger(id) || id <= 0)
    return <EmptyState title="Conta não encontrada" />
  if (isLoading || !data) return <Skeleton className="h-64 w-full" />

  const porId = new Map((instituicoes.data ?? []).map((i) => [i.id, i]))
  const efetiva = instituicaoEfetiva(data, porId)
  const nome = data.marketing_name ?? data.nome ?? "Conta"

  return (
    <div className="space-y-6">
      {/* Desktop já tem o breadcrumb; no mobile a topbar só mostra a página atual. */}
      <Button asChild variant="ghost" size="sm" className="-ml-2 md:hidden">
        <Link to="/contas">
          <ArrowLeft className="size-4" aria-hidden /> Contas e cartões
        </Link>
      </Button>

      <div className="flex items-start gap-3">
        <AvatarBanco nome={efetiva?.nome ?? nome} logoUrl={efetiva?.logo_url} />
        <div className="min-w-0 flex-1">
          <PageHeader
            titulo={nome}
            descricao={[
              efetiva?.nome,
              data.type === "CREDIT" ? "Cartão de crédito" : "Conta",
              data.numero ? mascarar(data.numero) : null,
            ]
              .filter(Boolean)
              .join(" · ")}
            acoes={
              <>
                <Button asChild variant="outline">
                  <Link to={`/transacoes?conta_id=${id}`}>
                    <ArrowRightLeft className="size-4" aria-hidden />
                    <span className="max-sm:sr-only">Transações</span>
                  </Link>
                </Button>
                {data.cartao ? (
                  <Button asChild variant="outline">
                    <Link to={`/faturas?cartao_id=${id}`}>
                      <CreditCard className="size-4" aria-hidden />
                      <span className="max-sm:sr-only">Faturas</span>
                    </Link>
                  </Button>
                ) : null}
              </>
            }
          />
        </div>
      </div>

      {data.type === "CREDIT" ? (
        <HeroCartao conta={data} nome={nome} logoUrl={efetiva?.logo_url} />
      ) : (
        <>
          <CardDestaque
            titulo="Saldo atual"
            centavos={data.saldo_centavos}
            mascote="money-v2"
          />
          <DetalheBanco
            conta={data}
            instituicao={efetiva?.nome ?? null}
            logoUrl={efetiva?.logo_url}
          />
        </>
      )}

      {data.cartao ? <GraficoFaturas contaId={id} /> : null}
    </div>
  )
}

const SUBTIPO: Record<string, string> = {
  CHECKING_ACCOUNT: "Conta corrente",
  SAVINGS_ACCOUNT: "Poupança",
  CREDIT_CARD: "Cartão de crédito",
}

/**
 * Tudo o que o Open Finance sabe da conta, sempre no mesmo lugar: o que o banco não informou
 * aparece como "—" em vez de sumir (a ausência também é informação).
 */
function DetalheBanco({
  conta,
  instituicao,
  logoUrl,
}: {
  conta: ContaDetalhe
  instituicao: string | null
  logoUrl?: string | null
}) {
  const b = conta.conta_bancaria
  const dinheiro = (v: number | null | undefined) =>
    v == null ? null : <Valor centavos={v} neutro />
  return (
    <Card>
      <CardHeader>
        <CardTitle>Detalhes da conta</CardTitle>
      </CardHeader>
      <CardContent>
        <dl className="grid grid-cols-1 gap-x-8 gap-y-5 text-sm sm:grid-cols-2 lg:grid-cols-3">
          <Campo rotulo="Instituição">
            {instituicao ? (
              <span className="flex items-center gap-2">
                <AvatarBanco
                  nome={instituicao}
                  logoUrl={logoUrl}
                  className="size-6 text-[0.625rem]"
                />
                {instituicao}
              </span>
            ) : null}
          </Campo>
          <Campo rotulo="Tipo">
            {(conta.subtype && SUBTIPO[conta.subtype]) ?? "Conta"}
          </Campo>
          <Campo rotulo="Número">
            {conta.numero ? mascarar(conta.numero) : null}
          </Campo>
          <Campo rotulo="Titular">{conta.owner}</Campo>
          <Campo rotulo="Saldo de fechamento">
            {dinheiro(b?.closing_balance_centavos)}
          </Campo>
          <Campo rotulo="Investido automaticamente">
            {dinheiro(b?.automatically_invested_balance_centavos)}
          </Campo>
          <Campo rotulo="Limite de cheque especial">
            {dinheiro(b?.overdraft_contracted_limit_centavos)}
          </Campo>
          <Campo rotulo="Cheque especial usado">
            {dinheiro(b?.overdraft_used_limit_centavos)}
          </Campo>
          <Campo rotulo="Atualizada pelo banco em">
            {conta.pluggy_atualizado_em
              ? formatDate(conta.pluggy_atualizado_em)
              : null}
          </Campo>
        </dl>
        {conta.saldos_reservados.length > 0 ? (
          <div className="mt-6 border-t pt-5">
            <p className="mb-2 text-xs font-semibold text-muted-foreground">
              Caixinhas
            </p>
            <ul className="space-y-1.5 text-sm">
              {conta.saldos_reservados.map((r) => (
                <li key={r.id} className="flex justify-between gap-3">
                  <span className="truncate">{r.nome ?? "Reserva"}</span>
                  <Valor centavos={r.valor_centavos ?? 0} neutro />
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}

function Campo({ rotulo, children }: { rotulo: string; children: ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs font-semibold text-muted-foreground">{rotulo}</dt>
      <dd className="mt-1 font-medium tabular-nums">
        {children ?? <span className="text-muted-foreground">—</span>}
      </dd>
    </div>
  )
}

/**
 * Cartão (que vira ao clicar) ao lado do herói. O número-âncora é a fatura atual — o saldo da
 * conta de crédito, o mesmo que a lista de Contas e cartões soma —; o limite fica de apoio.
 */
function HeroCartao({
  conta,
  nome,
  logoUrl,
}: {
  conta: ContaDetalhe
  nome: string
  logoUrl?: string | null
}) {
  const c = conta.cartao
  const [virado, setVirado] = useState(false)
  const virar = () => setVirado((v) => !v)
  const total = c?.credit_limit_centavos ?? null
  const disponivel = c?.available_credit_limit_centavos ?? null
  const usado =
    total != null && disponivel != null ? Math.max(total - disponivel, 0) : null
  const pct = usado != null && total ? Math.min(usado / total, 1) : null
  // Barra por estado (regra do DESIGN.md: nunca o accent): perto do limite avisa, estourado alerta.
  const corBarra =
    pct == null
      ? ""
      : pct >= 0.95
        ? "bg-negative"
        : pct >= 0.75
          ? "bg-warning"
          : "bg-success"

  return (
    <div className="grid items-center gap-5 @3xl:grid-cols-[minmax(0,19rem)_1fr] @3xl:gap-8">
      <div className="mx-auto w-full max-w-[19rem] space-y-2">
        <CartaoFlip
          conta={conta}
          nome={nome}
          logoUrl={logoUrl}
          virado={virado}
          onVirar={virar}
        />
        <div className="flex justify-center">
          <Button
            variant="ghost"
            size="sm"
            onClick={virar}
            aria-pressed={virado}
          >
            <RefreshCw className="size-4" aria-hidden /> Virar cartão
          </Button>
        </div>
      </div>

      <CardDestaque
        titulo="Fatura atual"
        centavos={Math.abs(conta.saldo_centavos)}
        estatisticas={[
          ...(disponivel != null
            ? [
                {
                  rotulo: "Limite disponível",
                  valor: formatBRL(disponivel),
                },
              ]
            : []),
          ...(total != null
            ? [{ rotulo: "Limite total", valor: formatBRL(total) }]
            : []),
          ...(c?.balance_close_date
            ? [
                {
                  rotulo: "Fechamento",
                  valor: formatDate(c.balance_close_date),
                },
              ]
            : []),
          ...(c?.balance_due_date
            ? [{ rotulo: "Vencimento", valor: formatDate(c.balance_due_date) }]
            : []),
          ...(c?.minimum_payment_centavos != null
            ? [
                {
                  rotulo: "Pagamento mínimo",
                  valor: formatBRL(c.minimum_payment_centavos),
                },
              ]
            : []),
        ]}
      >
        {pct != null && usado != null && total != null ? (
          <div className="max-w-xl space-y-2">
            <div
              className="h-2 overflow-hidden rounded-full bg-muted"
              role="progressbar"
              aria-label="Limite usado"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={Math.round(pct * 100)}
            >
              <div
                className={`h-full rounded-full ${corBarra}`}
                style={{ width: `${Math.max(pct * 100, 1)}%` }}
              />
            </div>
            <p className="text-sm text-muted-foreground">
              {formatBRL(usado)} do limite usados · {Math.round(pct * 100)}%
            </p>
          </div>
        ) : null}
      </CardDestaque>
    </div>
  )
}
