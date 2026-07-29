import { Landmark } from "lucide-react"
import { Link } from "react-router"

import { EmptyState } from "@/components/common/empty-state"
import { Valor } from "@/components/common/valor"
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

const GRID_CONTAS = "grid grid-cols-1 gap-4 sm:grid-cols-2"
const GRID_CARTOES = "grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3"

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
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Contas e Cartões</h1>
          {contas.length > 0 ? (
            <p className="text-sm text-muted-foreground">
              Saldo total em contas: <Valor centavos={saldoTotal} />
            </p>
          ) : null}
          {ultimaAtualizacao ? (
            <p className="mt-0.5 text-xs text-muted-foreground/70">
              Atualizado em {formatDateTime(ultimaAtualizacao)}
            </p>
          ) : null}
        </div>
        <SyncButton />
      </header>

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
          <Secao titulo="Contas" contas={contas} saldos={saldos} />
          <Secao titulo="Cartões" contas={cartoes} grid={GRID_CARTOES} />
        </>
      )}
    </div>
  )
}
