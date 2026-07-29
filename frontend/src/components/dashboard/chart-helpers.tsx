import type { ChartConfig } from "@/components/ui/chart"
import type { Granularidade, SerieBucket } from "@/lib/api/dashboard"
import { formatBRL, formatBucketLabel } from "@/lib/format"

const compacto = new Intl.NumberFormat("pt-BR", {
  notation: "compact",
  maximumFractionDigits: 1,
})

/** Formata o tick do eixo Y (centavos → reais compacto). Ex.: 123456 → `1,2 mil`. */
export const eixoBRL = (centavos: number) => compacto.format(centavos / 100)

/** Uma linha do tooltip: swatch + rótulo + valor em BRL (valores trafegam em centavos). */
export function linhaTooltip(
  valor: unknown,
  nome: string,
  cor: string | undefined,
  config: ChartConfig
) {
  return (
    <>
      <span
        className="mt-0.5 size-2.5 shrink-0 rounded-[2px]"
        style={{ background: cor }}
        aria-hidden
      />
      <div className="flex flex-1 items-center justify-between gap-2 leading-none">
        <span className="text-muted-foreground">{config[nome]?.label ?? nome}</span>
        <span className="font-mono font-medium tabular-nums text-foreground">
          {formatBRL(Number(valor))}
        </span>
      </div>
    </>
  )
}

// Rampa monocromática do tema (derivada de --primary por RCS em index.css; ordem fixa, nunca
// ciclada — a legenda é a codificação secundária). A 6ª cor existe p/ o "top 6" do gráfico de
// faturas; o dashboard usa só as 5 primeiras.
const CORES_CAT = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
  "var(--chart-6)",
]
const COR_OUTROS = "var(--muted-foreground)"

/**
 * Reduz os buckets às `n` maiores categorias (por volume no período) + "Outros", devolvendo o que
 * os gráficos empilhados/rosca consomem: `config` (slug→label/cor), `series` (ordem/cor fixas),
 * `linhas` (uma por bucket, valor por slug) e `fatias` (total por categoria, p/ rosca).
 */
export function prepararCategorias(
  buckets: SerieBucket[],
  rotulo: Map<string, string>,
  gran: Granularidade,
  n = 5
) {
  const total = new Map<string, number>()
  for (const b of buckets)
    for (const g of b.por_categoria) {
      const k = g.categoria_id ?? "sem"
      total.set(k, (total.get(k) ?? 0) + g.total_centavos)
    }
  const topIds = [...total.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, n)
    .map(([k]) => k)
  const idParaSlug = new Map(topIds.map((id, i) => [id, `c${i}`]))
  const nomeId = (id: string) =>
    id === "sem" ? "Sem categoria" : (rotulo.get(id) ?? id)

  const series = topIds.map((id, i) => ({
    slug: `c${i}`,
    nome: nomeId(id),
    cor: CORES_CAT[i % CORES_CAT.length],
  }))
  if (total.size > topIds.length) {
    series.push({ slug: "outros", nome: "Outros", cor: COR_OUTROS })
  }

  const config: ChartConfig = Object.fromEntries(
    series.map((s) => [s.slug, { label: s.nome, color: s.cor }])
  )

  const linhas = buckets.map((b) => {
    const linha: Record<string, number | string> = {
      label: formatBucketLabel(b.inicio, gran),
    }
    for (const s of series) linha[s.slug] = 0
    for (const g of b.por_categoria) {
      const slug = idParaSlug.get(g.categoria_id ?? "sem") ?? "outros"
      linha[slug] = (linha[slug] as number) + g.total_centavos
    }
    return linha
  })

  const porSlug = new Map<string, number>()
  for (const [id, v] of total)
    porSlug.set(
      idParaSlug.get(id) ?? "outros",
      (porSlug.get(idParaSlug.get(id) ?? "outros") ?? 0) + v
    )
  const fatias = series
    .map((s) => ({ nome: s.nome, cor: s.cor, valor: porSlug.get(s.slug) ?? 0 }))
    .filter((f) => f.valor > 0)

  return { config, series, linhas, fatias }
}
