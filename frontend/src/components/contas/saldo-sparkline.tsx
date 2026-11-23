import { useMemo } from "react"

import { Sparkline } from "@/components/common/graficos-base"
import type { SaldoDiarioPonto } from "@/lib/api/contas"
import { formatBRL, formatDate } from "@/lib/format"

/**
 * Saldo em conta dos últimos dias como área compacta (sparkline). Mesma receita da `AreaTendencia`
 * do painel: linha na cor primária + degradê que some, sem eixos (DESIGN.md "Restrained"). Vazio ou
 * série chapada → `null` (o card fica só com a identidade). */
export function SaldoSparkline({ pontos }: { pontos: SaldoDiarioPonto[] }) {
  const dados = useMemo(
    () => pontos.map((p) => ({ rotulo: p.data, valor: p.saldo_centavos })),
    [pontos]
  )
  if (pontos.length < 2) return null
  return (
    <Sparkline
      dados={dados}
      nome="Saldo"
      formatarRotulo={formatDate}
      formatarValor={formatBRL}
      ariaLabel="Saldo da conta nos últimos dias"
    />
  )
}
