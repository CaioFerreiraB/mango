import { Badge } from "@/components/ui/badge"
import type { EstadoRevisao } from "@/lib/revisao"
import { cn } from "@/lib/utils"

const ESTILO: Record<
  EstadoRevisao,
  { texto: string; badge: string; ponto: string }
> = {
  revisado: {
    texto: "Revisado",
    badge:
      "bg-[#e7f7ef] text-[#0ca678] dark:bg-emerald-500/15 dark:text-emerald-400",
    ponto: "bg-[#0ca678]",
  },
  pendente: {
    texto: "Pendente",
    badge:
      "bg-[#fdf0e6] text-[#f97316] dark:bg-amber-500/15 dark:text-amber-400",
    ponto: "bg-[#f97316]",
  },
  ignorado: {
    texto: "Ignorada",
    badge: "bg-muted text-muted-foreground",
    ponto: "bg-muted-foreground",
  },
}

const AJUDA_IGNORADA =
  "Anterior à data de início da revisão — não entra na fila. Ajuste em Configurações → Preferências."

/** Badge de revisão: fundo neutro suave, bolinha + texto coloridos — cor nunca é o único sentido. */
export function StatusBadge({ estado }: { estado: EstadoRevisao }) {
  const { texto, badge, ponto } = ESTILO[estado]
  return (
    <Badge
      variant="secondary"
      className={cn("gap-1.5 font-medium", badge)}
      title={estado === "ignorado" ? AJUDA_IGNORADA : undefined}
    >
      <span className={cn("size-1.5 rounded-full", ponto)} aria-hidden />
      {texto}
    </Badge>
  )
}
