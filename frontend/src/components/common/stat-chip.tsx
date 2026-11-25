import type { LucideIcon } from "lucide-react"

/** Chip de fato: ícone tintado do accent, valor destacado e rótulo — sobre painel translúcido
 *  para ficar legível por cima do gradiente/ilustração (dados sempre por cima). */
export function StatChip({
  icon: Icon,
  valor,
  rotulo,
}: {
  icon: LucideIcon
  valor: React.ReactNode
  rotulo: string
}) {
  return (
    <div className="rounded-xl border border-border/60 bg-background/70 p-2.5 backdrop-blur-sm sm:p-3">
      <span
        aria-hidden
        className="grid size-8 place-items-center rounded-lg bg-primary/10 text-primary"
      >
        <Icon className="size-4" />
      </span>
      <div className="mt-2 leading-tight">{valor}</div>
      <p className="text-xs text-muted-foreground">{rotulo}</p>
    </div>
  )
}
