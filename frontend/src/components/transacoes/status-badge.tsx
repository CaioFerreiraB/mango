import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

/** Badge de revisão: fundo neutro suave, bolinha + texto coloridos — cor nunca é o único sentido. */
export function StatusBadge({ revisada }: { revisada: boolean }) {
  return (
    <Badge
      variant="secondary"
      className={cn(
        "gap-1.5 font-medium",
        revisada
          ? "bg-[#e7f7ef] text-[#0ca678] dark:bg-emerald-500/15 dark:text-emerald-400"
          : "bg-[#fdf0e6] text-[#f97316] dark:bg-amber-500/15 dark:text-amber-400"
      )}
    >
      <span
        className={cn(
          "size-1.5 rounded-full",
          revisada ? "bg-[#0ca678]" : "bg-[#f97316]"
        )}
        aria-hidden
      />
      {revisada ? "Revisado" : "Pendente"}
    </Badge>
  )
}
