import type { LucideIcon } from "lucide-react"

import { cn } from "@/lib/utils"

/** Cartão de opção única (wizard de nova divisão — "quem pagou"/"como dividir"): título +
 *  descrição, destacado quando selecionado. Padrão novo (sem precedente no app), pensado pra
 *  ser reaproveitado nos dois passos do wizard que usam esse formato. */
export function OpcaoCard({
  icon: Icon,
  titulo,
  descricao,
  selecionado,
  onClick,
}: {
  icon: LucideIcon
  titulo: string
  descricao: string
  selecionado: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selecionado}
      className={cn(
        "flex flex-col items-start gap-1 rounded-lg border p-3 text-left transition-colors hover:bg-muted/50",
        selecionado && "border-primary bg-primary/5 hover:bg-primary/5"
      )}
    >
      <Icon
        className={cn(
          "size-5",
          selecionado ? "text-primary" : "text-muted-foreground"
        )}
      />
      <span
        className={cn("text-sm font-medium", selecionado && "text-primary")}
      >
        {titulo}
      </span>
      <span className="text-xs text-muted-foreground">{descricao}</span>
    </button>
  )
}
