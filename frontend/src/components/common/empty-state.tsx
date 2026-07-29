import type { LucideIcon } from "lucide-react"
import type { ReactNode } from "react"

import { cn } from "@/lib/utils"

type EmptyStateProps = {
  icon?: LucideIcon
  title: string
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
  title,
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
      {Icon ? (
        <div className="flex size-12 items-center justify-center rounded-full bg-muted text-muted-foreground">
          <Icon className="size-6" aria-hidden />
        </div>
      ) : null}
      <div className="space-y-1.5">
        <p className="text-base font-medium text-foreground">{title}</p>
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
