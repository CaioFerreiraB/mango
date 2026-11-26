import { Plus } from "lucide-react"
import { useState } from "react"

import { EmptyState } from "@/components/common/empty-state"
import { CardDestaque, Kpi } from "@/components/common/kpi"
import { PageHeader } from "@/components/common/page-header"
import { Selo } from "@/components/common/selo"
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
      <PageHeader
        titulo="Objetivos"
        descricao="Metas alimentadas pelo saldo das contas e investimentos vinculados."
        acoes={
          <ObjetivoFormDialog
            trigger={
              <Button>
                <Plus className="size-4" aria-hidden />
                <span className="max-sm:sr-only">Novo objetivo</span>
              </Button>
            }
          />
        }
      />

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
          cena="goal"
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

/** Topo: o herói (total alocado, mascote do módulo) ocupa duas colunas do grid; os KPIs de
 *  metas concluídas e investido sem objetivo completam a linha. */
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
  const concluidos = objetivos.filter((o) => o.progresso >= 1).length
  const invs = investimentos.data ?? []
  const totalInvestido = invs.reduce((s, i) => s + liquido(i), 0)
  const livre = invs
    .filter((i) => i.objetivo_id == null)
    .reduce((s, i) => s + liquido(i), 0)

  return (
    <>
      <CardDestaque
        className="sm:col-span-2"
        titulo="Alocado em objetivos"
        centavos={alocado}
        mascote="goal"
        rodape={`${pct}% das metas alcançadas`}
      />
      <Kpi
        label="Metas concluídas"
        valor={`${concluidos} de ${objetivos.length}`}
        detalhe={
          <>
            Faltam <Valor centavos={Math.max(alvo - atingido, 0)} neutro /> no
            total
          </>
        }
      />
      {investimentos.isLoading ? (
        <Skeleton className="h-full min-h-24 w-full rounded-xl" />
      ) : investimentos.isError ? (
        <p className="flex items-center justify-center rounded-xl border border-dashed p-4 text-sm text-muted-foreground">
          Não foi possível carregar os investimentos.
        </p>
      ) : (
        <Kpi
          label="Investido sem objetivo"
          valor={<Valor centavos={livre} neutro />}
          // Não conta posições: compras de um mesmo ativo (caixinhas) inflariam o número.
          detalhe={
            totalInvestido
              ? `${Math.round((livre / totalInvestido) * 100)}% do total investido`
              : "Nenhum investimento"
          }
        />
      )}
    </>
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
    <Card className="relative superficie-interativa has-[button:focus-visible]:ring-[3px] has-[button:focus-visible]:ring-ring/50">
      <CardHeader className="pb-2">
        <button
          type="button"
          onClick={onAbrir}
          className="text-left font-medium [overflow-wrap:anywhere] break-words outline-none after:absolute after:inset-0 after:rounded-xl"
        >
          {objetivo.titulo}
        </button>
        {objetivo.progresso >= 1 ? (
          <Selo tom="sucesso" className="w-fit">
            Concluído
          </Selo>
        ) : null}
        {objetivo.descricao ? (
          <p className="line-clamp-2 text-xs text-muted-foreground">
            {objetivo.descricao}
          </p>
        ) : null}
      </CardHeader>
      <CardContent className="space-y-2">
        <Progress value={pct} className="bg-primary/10" />
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
