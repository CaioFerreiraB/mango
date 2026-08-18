import { Cell, Pie, PieChart } from "recharts"

import { ChartContainer } from "@/components/ui/chart"

/** Um anel de progresso com o % e um rótulo centralizados. Extraído de
 * `objetivos/objetivo-detalhe-dialog.tsx` (era um componente local ali) — agora reaproveitado
 * também no resumo do mês de orçamentos. Variante maior do padrão usado no drawer de ativos
 * (`DonutParticipacao`, ativo-drawer.tsx). */
export function AnelProgresso({
  pct,
  rotulo = "atingido",
  tamanho = 140,
}: {
  pct: number
  rotulo?: string
  tamanho?: number
}) {
  const valor = Math.max(0, Math.min(100, pct))
  const dados = [
    { nome: "fatia", v: valor },
    { nome: "resto", v: 100 - valor },
  ]
  const raioExterno = tamanho * 0.485
  const raioInterno = raioExterno * 0.765
  return (
    <div className="relative mx-auto shrink-0">
      <ChartContainer config={{}} className="aspect-square" style={{ height: tamanho }}>
        <PieChart>
          <Pie
            data={dados}
            dataKey="v"
            nameKey="nome"
            innerRadius={raioInterno}
            outerRadius={raioExterno}
            startAngle={90}
            endAngle={-270}
            strokeWidth={0}
            isAnimationActive={false}
          >
            <Cell fill="var(--primary)" />
            <Cell fill="var(--muted)" />
          </Pie>
        </PieChart>
      </ChartContainer>
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
        {/* Nunca negativo no texto (mesmo que `pct` venha assim por algum motivo) — só o
            excesso acima de 100% continua visível (não é capado aqui, só o arco é). */}
        <span className="text-2xl font-bold text-accent-ink tabular-nums">
          {Math.max(0, Math.round(pct))}%
        </span>
        <span className="text-xs text-muted-foreground">{rotulo}</span>
      </div>
    </div>
  )
}
