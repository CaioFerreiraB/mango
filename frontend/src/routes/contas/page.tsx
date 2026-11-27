import { Landmark } from "lucide-react"
import { useMemo } from "react"
import { Link } from "react-router"

import { EmptyState } from "@/components/common/empty-state"
import { CardDestaque } from "@/components/common/kpi"
import { PageHeader } from "@/components/common/page-header"
import { ContaCard } from "@/components/contas/conta-card"
import { SyncButton } from "@/components/sync-button"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Sparkline } from "@/components/common/graficos-base"
import { Valor } from "@/components/common/valor"
import { formatBRL, formatDate, formatDateTime } from "@/lib/format"
import {
  useContas,
  useContasSaldosDiarios,
  useSaldoContasSerie,
  type Conta,
  type SaldoDiarioPonto,
} from "@/lib/api/contas"

const GRID_CONTAS = "grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3"
const GRID_CARTOES =
  "grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4"

function Secao({
  titulo,
  contas,
  saldos,
  grid = GRID_CONTAS,
}: {
  titulo: string
  contas: Conta[]
  saldos?: Map<number, SaldoDiarioPonto[]>
  grid?: string
}) {
  if (contas.length === 0) return null
  return (
    <section className="space-y-3">
      <h2 className="text-sm font-medium text-muted-foreground">{titulo}</h2>
      <div className={grid}>
        {contas.map((c) => (
          <ContaCard key={c.id} conta={c} pontos={saldos?.get(c.id)} />
        ))}
      </div>
    </section>
  )
}

export function ContasPage() {
  const { data, isLoading, isError } = useContas()
  const { data: saldos } = useContasSaldosDiarios()

  const contas = (data ?? []).filter((c) => c.type === "BANK")
  const cartoes = (data ?? []).filter((c) => c.type === "CREDIT")
  const saldoTotal = contas.reduce((s, c) => s + c.saldo_centavos, 0)
  const faturas = cartoes.reduce((s, c) => s + c.saldo_centavos, 0)
  const pontos = useSaldoContasSerie()
  const serie = useMemo(
    () => pontos.map((p) => ({ rotulo: p.data, valor: p.saldo_centavos })),
    [pontos]
  )
  // ISO ordena cronologicamente → o mais recente é o max lexicográfico.
  const ultimaAtualizacao = (data ?? [])
    .map((c) => c.pluggy_atualizado_em)
    .filter((d): d is string => Boolean(d))
    .sort()
    .at(-1)

  return (
    <div className="space-y-6">
      <PageHeader
        titulo="Contas e cartões"
        descricao={
          ultimaAtualizacao
            ? `Saldos e limites vindos do Open Finance · atualizado em ${formatDateTime(ultimaAtualizacao)}`
            : "Saldos e limites vindos do Open Finance."
        }
        acoes={<SyncButton />}
      />

      {isError ? (
        <EmptyState title="Não foi possível carregar as contas" />
      ) : isLoading ? (
        <div className={GRID_CONTAS}>
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-32 w-full" />
          ))}
        </div>
      ) : (data ?? []).length === 0 ? (
        <EmptyState
          icon={Landmark}
          title="Nenhuma conta conectada"
          description="Conecte o Open Finance para importar suas contas e cartões."
        >
          <Button asChild>
            <Link to="/configuracoes">Conectar conta</Link>
          </Button>
        </EmptyState>
      ) : (
        <>
          {contas.length ? (
            <CardDestaque
              titulo="Saldo em contas"
              centavos={saldoTotal}
              mascote="money"
              rodape={
                contas.length === 1 ? "1 conta" : `${contas.length} contas`
              }
              estatisticas={
                cartoes.length
                  ? [
                      {
                        rotulo:
                          cartoes.length === 1
                            ? "Fatura do cartão"
                            : `Faturas de ${cartoes.length} cartões`,
                        valor: <Valor centavos={faturas} absoluto neutro />,
                      },
                    ]
                  : undefined
              }
              grafico={
                serie.length >= 2 ? (
                  <Sparkline
                    dados={serie}
                    nome="Saldo"
                    altura={80}
                    formatarRotulo={formatDate}
                    formatarValor={formatBRL}
                    ariaLabel="Saldo somado das contas nos últimos 30 dias"
                  />
                ) : undefined
              }
            />
          ) : (
            // Só cartões conectados: "Saldo em contas R$ 0,00 · 0 contas" seria um número falso —
            // o número-âncora passa a ser o que se deve nas faturas.
            <CardDestaque
              titulo={
                cartoes.length === 1
                  ? "Fatura do cartão"
                  : "Faturas dos cartões"
              }
              centavos={Math.abs(faturas)}
              mascote="money"
              rodape={
                cartoes.length === 1 ? "1 cartão" : `${cartoes.length} cartões`
              }
            />
          )}
          <Secao titulo="Contas" contas={contas} saldos={saldos} />
          <Secao titulo="Cartões" contas={cartoes} grid={GRID_CARTOES} />
        </>
      )}
    </div>
  )
}
