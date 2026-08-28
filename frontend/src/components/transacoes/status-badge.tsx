import { Badge } from "@/components/ui/badge"
import type { EstadoRevisao } from "@/lib/revisao"
import { cn } from "@/lib/utils"

const AJUDA_IGNORADA =
  "Anterior à data de início da revisão — não entra na fila. Ajuste em Configurações → Preferências."

/** Texto e cores de cada estado. `switch` exaustivo: o TS garante que nenhum estado fica de fora. */
function estilo(estado: EstadoRevisao) {
  switch (estado) {
    case "revisado":
      return {
        texto: "Revisado",
        badge:
          "bg-[#e7f7ef] text-[#0ca678] dark:bg-emerald-500/15 dark:text-emerald-400",
        ponto: "bg-[#0ca678]",
      }
    case "pendente":
      return {
        texto: "Pendente",
        badge:
          "bg-[#fdf0e6] text-[#f97316] dark:bg-amber-500/15 dark:text-amber-400",
        ponto: "bg-[#f97316]",
      }
    case "ignorado":
      return {
        texto: "Ignorada",
        badge: "bg-muted text-muted-foreground",
        ponto: "bg-muted-foreground",
      }
  }
}

/** Badge de revisão: fundo neutro suave, bolinha + texto coloridos — cor nunca é o único sentido. */
export function StatusBadge({
  estado,
  className,
}: {
  estado: EstadoRevisao
  className?: string
}) {
  const { texto, badge, ponto } = estilo(estado)
  return (
    <Badge
      variant="secondary"
      className={cn("gap-1.5 font-medium", badge, className)}
      title={estado === "ignorado" ? AJUDA_IGNORADA : undefined}
    >
      <span className={cn("size-1.5 rounded-full", ponto)} aria-hidden />
      {texto}
    </Badge>
  )
}
