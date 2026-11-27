import { CalendarCheck, ChevronRight } from "lucide-react"
import type { ReactNode } from "react"
import { Link } from "react-router"

import { Valor } from "@/components/common/valor"
import { CardGrafico } from "@/components/dashboard/card-grafico"
import { BarraMes } from "@/components/despesas-fixas/barra-mes"
import { estiloSituacao } from "@/components/despesas-fixas/situacao"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import {
  useResumoDespesasFixas,
  type DespesaFixaResumo,
} from "@/lib/api/despesas-fixas"
import { formatDataISO, formatMesAno } from "@/lib/format"
import { cn } from "@/lib/utils"

// Dois widgets sobre o mesmo `/resumo` (uma requisição, cache compartilhado): o gráfico do mês e
// a lista dos próximos vencimentos. Tudo leva à página de Despesas fixas.

/** Card + estados comuns (carregando, erro, sem despesas); `children` só com dados. */
function Moldura({
  titulo,
  descricao,
  children,
}: {
  titulo: string
  /** Sem ela, o mês do resumo. */
  descricao?: string
  children: (r: DespesaFixaResumo) => ReactNode
}) {
  const resumo = useResumoDespesasFixas()
  const r = resumo.data
  return (
    <CardGrafico
      titulo={titulo}
      descricao={
        descricao ??
        (r ? `Vencimentos de ${formatMesAno(`${r.mes}-15`)}` : undefined)
      }
      acao={
        <Button asChild variant="ghost" size="sm">
          <Link to="/despesas-fixas">
            Ver todas <ChevronRight className="size-4" />
          </Link>
        </Button>
      }
    >
      {resumo.isLoading ? (
        <Skeleton className="h-32 w-full" />
      ) : resumo.isError || !r ? (
        <p className="py-6 text-center text-sm text-muted-foreground">
          Não foi possível carregar as despesas fixas.
        </p>
      ) : !r.tem_despesas ? (
        <div className="flex flex-col items-center gap-3 py-6 text-center">
          <CalendarCheck className="size-6 text-muted-foreground" aria-hidden />
          <p className="text-sm text-muted-foreground">
            Cadastre aluguel, contas e parcelas para ver aqui o que já foi pago
            e o que está atrasado.
          </p>
          <Button asChild size="sm" variant="secondary">
            <Link to="/despesas-fixas">Cadastrar despesa fixa</Link>
          </Button>
        </div>
      ) : (
        children(r)
      )}
    </CardGrafico>
  )
}

/** Gráfico do mês: pagas × total, barra empilhada e valor de cada estado. */
export function DespesasFixasMesWidget() {
  return (
    <Moldura titulo="Despesas fixas · visão geral">
      {(r) => {
        const total = r.pagas.qtd + r.abertas.qtd + r.atrasadas.qtd
        return (
          <div className="space-y-4">
            <p className="text-3xl font-bold tabular-nums">
              {r.pagas.qtd}{" "}
              <span className="text-base font-medium text-muted-foreground">
                de {total} pagas
              </span>
            </p>
            <BarraMes resumo={r} />
            <dl className="space-y-1.5 text-sm">
              <Contagem
                ponto="bg-success"
                rotulo={r.pagas.qtd === 1 ? "paga" : "pagas"}
                {...r.pagas}
              />
              <Contagem
                ponto="bg-muted-foreground"
                rotulo="em aberto"
                {...r.abertas}
              />
              <Contagem
                ponto="bg-negative"
                rotulo={r.atrasadas.qtd === 1 ? "atrasada" : "atrasadas"}
                destaque={r.atrasadas.qtd > 0}
                {...r.atrasadas}
              />
            </dl>
          </div>
        )
      }}
    </Moldura>
  )
}

/** Próximos vencimentos, atrasados primeiro (o backend já ordena). */
export function DespesasFixasProximosWidget() {
  return (
    <Moldura titulo="Despesas fixas · lista" descricao="Atrasadas primeiro">
      {(r) =>
        r.proximos.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            Nada em aberto. Tudo em dia.
          </p>
        ) : (
          <ul className="divide-y">
            {r.proximos.map((p) => {
              const atrasada = p.situacao === "atrasada"
              return (
                <li key={p.ocorrencia_id}>
                  <Link
                    to="/despesas-fixas"
                    className="flex items-center gap-3 rounded-md py-2 transition-colors hover:bg-muted/50"
                  >
                    <span
                      aria-hidden
                      className={cn(
                        "size-2 shrink-0 rounded-full",
                        estiloSituacao(p.situacao).ponto
                      )}
                    />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium">
                        {p.descricao}
                      </span>
                      <span
                        className={cn(
                          "block text-xs",
                          atrasada
                            ? "text-negative-ink"
                            : "text-muted-foreground"
                        )}
                      >
                        {atrasada
                          ? `Atrasada · venceu ${formatDataISO(p.vencimento)}`
                          : p.situacao === "vence_hoje"
                            ? "Vence hoje"
                            : `Vence ${formatDataISO(p.vencimento)}`}
                      </span>
                    </span>
                    <Valor
                      centavos={p.valor_centavos}
                      neutro
                      className="text-sm font-semibold"
                    />
                  </Link>
                </li>
              )
            })}
          </ul>
        )
      }
    </Moldura>
  )
}

function Contagem({
  ponto,
  rotulo,
  qtd,
  centavos,
  destaque = false,
}: {
  ponto: string
  rotulo: string
  qtd: number
  centavos: number
  destaque?: boolean
}) {
  return (
    <div className="flex items-center gap-2">
      <span aria-hidden className={cn("size-2 shrink-0 rounded-full", ponto)} />
      <dt className={cn("flex-1", destaque && "font-medium text-negative-ink")}>
        {qtd} {rotulo}
      </dt>
      <dd>
        <Valor centavos={centavos} neutro className="font-medium" />
      </dd>
    </div>
  )
}
