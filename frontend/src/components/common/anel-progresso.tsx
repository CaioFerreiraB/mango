import { Rosca } from "@/components/common/graficos-base"

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
  return (
    <div className="relative mx-auto shrink-0">
      <Rosca
        fatias={[
          { nome: "atingido", valor, cor: "var(--primary)" },
          { nome: "restante", valor: 100 - valor, cor: "var(--muted)" },
        ]}
        tamanho={tamanho}
        espessura={0.235}
        ariaLabel={`${Math.max(0, Math.round(pct))}% ${rotulo}`}
      />
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
