import type { LucideIcon } from "lucide-react"
import type { ReactNode } from "react"

import { Mascote } from "@/components/common/mascote"
import type { Cena } from "@/lib/illustrations"
import { cn } from "@/lib/utils"

type EmptyStateProps = {
  icon?: LucideIcon
  /** Mascote no lugar do ícone — para os vazios "de momento" (primeiro uso, nada a fazer). */
  cena?: Cena
  title: string
  /** Quando o vazio É a página (404), o título vira o `h1`. */
  tituloComo?: "p" | "h1"
  description?: string
  /** Ação(ões) — ex.: um botão para conectar uma conta. */
  children?: ReactNode
  className?: string
}

/**
 * Estado vazio que **ensina** a interface (não apenas "nada aqui"). Base reutilizável para listas
 * sem dados, telas em construção e erros de carregamento.
 */
export function EmptyState({
  icon: Icon,
  cena,
  title,
  tituloComo: Titulo = "p",
  description,
  children,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-4 rounded-xl border border-dashed px-6 py-16 text-center",
        className
      )}
    >
      {cena ? (
        <Mascote cena={cena} className="h-28 w-auto" />
      ) : Icon ? (
        <div className="flex size-12 items-center justify-center rounded-full bg-muted text-muted-foreground">
          <Icon className="size-6" aria-hidden />
        </div>
      ) : null}
      <div className="space-y-1.5">
        <Titulo className="text-base font-medium text-foreground">
          {title}
        </Titulo>
        {description ? (
          <p className="mx-auto max-w-md text-sm text-balance text-muted-foreground">
            {description}
          </p>
        ) : null}
      </div>
      {children ? (
        <div className="flex flex-wrap items-center justify-center gap-2">
          {children}
        </div>
      ) : null}
    </div>
  )
}
