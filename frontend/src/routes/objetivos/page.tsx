import { Plus, Target } from "lucide-react"
import { useState } from "react"

import { EmptyState } from "@/components/common/empty-state"
import { CardDestaque } from "@/components/dashboard/kpi-card"
import { Valor } from "@/components/common/valor"
import { ObjetivoDetalheDialog } from "@/components/objetivos/objetivo-detalhe-dialog"
import { ObjetivoFormDialog } from "@/components/objetivos/objetivo-form-dialog"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Skeleton } from "@/components/ui/skeleton"
import { useInvestimentos, type Investimento } from "@/lib/api/investimentos"
import { useObjetivos, type Objetivo } from "@/lib/api/objetivos"

const GRID = "grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4"

export function ObjetivosPage() {
  const { data, isLoading, isError } = useObjetivos()
  const [detalhe, setDetalhe] = useState<number | null>(null)

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Objetivos</h1>
          <p className="text-sm text-muted-foreground">
            Metas financeiras alimentadas pelo saldo das contas e investimentos
            vinculados.
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
          <Resumo objetivos={data ?? []} />
          {(data ?? []).map((o) => (
            <ObjetivoCard
              key={o.id}
              objetivo={o}
              onAbrir={() => setDetalhe(o.id)}
            />
          ))}
        </div>
      )}

      {detalhe !== null ? (
        <ObjetivoDetalheDialog id={detalhe} onClose={() => setDetalhe(null)} />
      ) : null}
    </div>
  )
}

/** Valor líquido (bruto − IR − IOF): mesma regra de `valor_liquido` no backend, que é o que os
 *  objetivos somam — os dois cards do topo ficam na mesma base. */
function liquido(i: Investimento) {
  return (
    (i.amount_centavos ?? i.saldo_centavos) -
    (i.taxes_centavos ?? 0) -
    (i.taxes2_centavos ?? 0)
  )
}

/** Topo: total alocado (destaque escuro) + investido sem objetivo (variante suave). Ocupam a
 *  linha inteira do grid, meio a meio a partir de `sm`. */
function Resumo({ objetivos }: { objetivos: Objetivo[] }) {
  const investimentos = useInvestimentos()
  const alocado = objetivos.reduce((s, o) => s + o.valor_guardado_centavos, 0)
  const alvo = objetivos.reduce((s, o) => s + o.valor_alvo_centavos, 0)
  // Excesso de um objetivo não completa outro: cada um contribui no máximo com o próprio alvo.
  const atingido = objetivos.reduce(
    (s, o) => s + Math.min(o.valor_guardado_centavos, o.valor_alvo_centavos),
    0
  )
  const pct = alvo ? Math.floor((atingido / alvo) * 100) : 0
  const invs = investimentos.data ?? []
  const totalInvestido = invs.reduce((s, i) => s + liquido(i), 0)
  const livre = invs
    .filter((i) => i.objetivo_id == null)
    .reduce((s, i) => s + liquido(i), 0)

  return (
    <div className="col-span-full grid gap-4 sm:grid-cols-2">
      <CardDestaque
        titulo="Alocado em objetivos"
        centavos={alocado}
        oculto={false}
        rodape={`${pct}% das metas alcançadas`}
      />
      {investimentos.isLoading ? (
        <Skeleton className="h-full min-h-32 w-full rounded-xl" />
      ) : investimentos.isError ? (
        <p className="flex items-center justify-center rounded-xl border border-dashed p-4 text-sm text-muted-foreground">
          Não foi possível carregar os investimentos.
        </p>
      ) : (
        <CardDestaque
          suave
          titulo="Investido sem objetivo"
          centavos={livre}
          oculto={false}
          // Não conta posições: compras de um mesmo ativo (caixinhas) inflariam o número.
          rodape={
            totalInvestido
              ? `${Math.round((livre / totalInvestido) * 100)}% do total investido`
              : "Nenhum investimento"
          }
        />
      )}
    </div>
  )
}

function ObjetivoCard({
  objetivo,
  onAbrir,
}: {
  objetivo: Objetivo
  onAbrir: () => void
}) {
  const pct = Math.round(objetivo.progresso * 100)
  return (
    // O título é o botão (alvo de teclado/leitor de tela); o ::after dele estica o clique ao card
    // inteiro. Antes era um <div onClick> — inalcançável sem mouse.
    <Card className="relative transition-colors hover:border-primary/50 has-[button:focus-visible]:ring-[3px] has-[button:focus-visible]:ring-ring/50">
      <CardHeader className="pb-2">
        <button
          type="button"
          onClick={onAbrir}
          className="text-left font-medium [overflow-wrap:anywhere] break-words outline-none after:absolute after:inset-0 after:rounded-xl"
        >
          {objetivo.titulo}
        </button>
        {objetivo.descricao ? (
          <p className="line-clamp-2 text-xs text-muted-foreground">
            {objetivo.descricao}
          </p>
        ) : null}
      </CardHeader>
      <CardContent className="space-y-2">
        <Progress value={pct} />
        <div className="flex flex-wrap items-baseline justify-between gap-x-2 text-sm">
          <Valor
            centavos={objetivo.valor_guardado_centavos}
            neutro
            className="text-base"
          />
          <span className="text-muted-foreground">
            de <Valor centavos={objetivo.valor_alvo_centavos} neutro /> ({pct}%)
          </span>
        </div>
      </CardContent>
    </Card>
  )
}
