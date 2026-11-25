import { Landmark } from "lucide-react"
import { Link } from "react-router"

import { EmptyState } from "@/components/common/empty-state"
import { CardDestaque } from "@/components/common/kpi"
import { PageHeader } from "@/components/common/page-header"
import { ContaCard } from "@/components/contas/conta-card"
import { SyncButton } from "@/components/sync-button"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { formatDateTime } from "@/lib/format"
import {
  useContas,
  useContasSaldosDiarios,
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
          <CardDestaque
            className="sm:max-w-md"
            titulo="Saldo em contas"
            centavos={saldoTotal}
            mascote="money"
            rodape={contas.length === 1 ? "1 conta" : `${contas.length} contas`}
          />
          <Secao titulo="Contas" contas={contas} saldos={saldos} />
          <Secao titulo="Cartões" contas={cartoes} grid={GRID_CARTOES} />
        </>
      )}
    </div>
  )
}
