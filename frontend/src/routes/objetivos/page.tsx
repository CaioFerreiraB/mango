import { Plus, Target } from "lucide-react"
import { useState } from "react"

import { EmptyState } from "@/components/common/empty-state"
import { Valor } from "@/components/common/valor"
import { ObjetivoDetalheDialog } from "@/components/objetivos/objetivo-detalhe-dialog"
import { ObjetivoFormDialog } from "@/components/objetivos/objetivo-form-dialog"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Skeleton } from "@/components/ui/skeleton"
import { useObjetivos, type Objetivo } from "@/lib/api/objetivos"

const GRID = "grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3"

export function ObjetivosPage() {
  const { data, isLoading, isError } = useObjetivos()
  const [detalhe, setDetalhe] = useState<number | null>(null)

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Objetivos</h1>
          <p className="text-sm text-muted-foreground">
            Metas financeiras alimentadas pelo saldo das contas e investimentos vinculados.
          </p>
        </div>
        <ObjetivoFormDialog
          trigger={
            <Button>
              <Plus className="size-4" /> Novo objetivo
            </Button>
          }
        />
      </header>

      {isError ? (
        <EmptyState title="Não foi possível carregar os objetivos" />
      ) : isLoading ? (
        <div className={GRID}>
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-36 w-full" />
          ))}
        </div>
      ) : (data ?? []).length === 0 ? (
        <EmptyState
          icon={Target}
          title="Nenhum objetivo ainda"
          description="Crie uma meta (viagem, reserva de emergência…) e vincule contas ou investimentos para acompanhar o progresso."
        >
          <ObjetivoFormDialog
            trigger={
              <Button>
                <Plus className="size-4" /> Novo objetivo
              </Button>
            }
          />
        </EmptyState>
      ) : (
        <div className={GRID}>
          {(data ?? []).map((o) => (
            <ObjetivoCard key={o.id} objetivo={o} onAbrir={() => setDetalhe(o.id)} />
          ))}
        </div>
      )}

      {detalhe !== null ? (
        <ObjetivoDetalheDialog id={detalhe} onClose={() => setDetalhe(null)} />
      ) : null}
    </div>
  )
}

function ObjetivoCard({ objetivo, onAbrir }: { objetivo: Objetivo; onAbrir: () => void }) {
  const pct = Math.round(objetivo.progresso * 100)
  return (
    <Card className="cursor-pointer transition-colors hover:border-primary/50" onClick={onAbrir}>
      <CardHeader className="pb-2">
        <p className="font-medium break-words [overflow-wrap:anywhere]">{objetivo.titulo}</p>
        {objetivo.descricao ? (
          <p className="line-clamp-2 text-xs text-muted-foreground">{objetivo.descricao}</p>
        ) : null}
      </CardHeader>
      <CardContent className="space-y-2">
        <Progress value={pct} />
        <div className="flex items-baseline justify-between text-sm">
          <Valor centavos={objetivo.valor_guardado_centavos} neutro className="text-base" />
          <span className="text-muted-foreground">
            de <Valor centavos={objetivo.valor_alvo_centavos} neutro /> ({pct}%)
          </span>
        </div>
      </CardContent>
    </Card>
  )
}
