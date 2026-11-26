import { useMemo, useState } from "react"

import { GraficoBarras } from "@/components/common/graficos-base"
import { eixoBRL } from "@/components/dashboard/chart-helpers"
import { BarrasEmpilhadasCategorias } from "@/components/dashboard/graficos"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { useMapaCategorias } from "@/lib/api/categorias"
import { useFaturasResumo, type FaturaResumoBucket } from "@/lib/api/contas"
import type { SerieBucket } from "@/lib/api/dashboard"
import { formatBRL, formatBucketLabel } from "@/lib/format"

type Modo = "total" | "categoria"

/** Total de cada fatura como barra única na cor primária. */
function BarrasTotal({ buckets }: { buckets: FaturaResumoBucket[] }) {
  const dados = useMemo(
    () =>
      buckets.map((b) => ({
        label: formatBucketLabel(b.due_date, "mensal"),
        total: b.total_centavos,
      })),
    [buckets]
  )
  return (
    <GraficoBarras
      dados={dados}
      x="label"
      chave="total"
      nome="Total da fatura"
      formatarY={eixoBRL}
      formatarValor={formatBRL}
      ariaLabel="Total de cada fatura"
    />
  )
}

/**
 * Gráfico das últimas faturas do cartão. Alterna entre o total (barra na cor primária) e a quebra
 * por categoria (top 6 + "Outros", barras empilhadas). Cada fatura vira um bucket mensal (só
 * `por_categoria` é lido; o rótulo sai do vencimento).
 */
export function GraficoFaturas({ contaId }: { contaId: number }) {
  const [modo, setModo] = useState<Modo>("total")
  const { data: buckets, isLoading } = useFaturasResumo(contaId)
  // Rótulo do segmento sintético que fecha a quebra no total (AJUSTE_CATEGORIA_ID no backend):
  // encargos (IOF/juros/multa), saldo anterior e estornos que não são compras categorizáveis.
  const rotulo = new Map(useMapaCategorias()).set(
    "__ajuste__",
    "Encargos e ajustes"
  )

  // Cartão sem faturas ainda: nada a mostrar (não polui o detalhe com um card vazio).
  if (!isLoading && (buckets?.length ?? 0) === 0) return null

  const serie: SerieBucket[] = (buckets ?? []).map((b) => ({
    inicio: b.due_date,
    entradas_centavos: 0,
    saidas_centavos: 0,
    resultado_centavos: 0,
    investido_centavos: 0,
    por_categoria: b.por_categoria,
  }))

  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between gap-4">
        <div>
          <CardTitle>Últimas faturas</CardTitle>
          <CardDescription>
            {modo === "categoria"
              ? "Valor por fatura, dividido por categoria"
              : "Valor total de cada fatura"}
          </CardDescription>
        </div>
        <ToggleGroup
          type="single"
          size="sm"
          variant="outline"
          spacing={0}
          value={modo}
          onValueChange={(v) => v && setModo(v as Modo)}
        >
          <ToggleGroupItem value="total">Total</ToggleGroupItem>
          <ToggleGroupItem value="categoria">Por categoria</ToggleGroupItem>
        </ToggleGroup>
      </CardHeader>
      <CardContent>
        {isLoading || !buckets ? (
          <Skeleton className="h-[240px] w-full" />
        ) : modo === "categoria" ? (
          <BarrasEmpilhadasCategorias
            buckets={serie}
            granularidade="mensal"
            rotulo={rotulo}
          />
        ) : (
          <BarrasTotal buckets={buckets} />
        )}
      </CardContent>
    </Card>
  )
}
