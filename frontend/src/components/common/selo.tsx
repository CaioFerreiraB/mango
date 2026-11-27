import type { ReactNode } from "react"

import { Badge } from "@/components/ui/badge"
import { TONS_SELO, type TomSelo } from "@/components/common/selo-tons"
import { cn } from "@/lib/utils"

export function Selo({
  tom,
  children,
  title,
  className,
}: {
  tom: TomSelo
  children: ReactNode
  title?: string
  className?: string
}) {
  const { badge, ponto } = TONS_SELO[tom]
  return (
    <Badge
      variant="secondary"
      className={cn("gap-1.5 font-medium", badge, className)}
      title={title}
    >
      <span className={cn("size-1.5 rounded-full", ponto)} aria-hidden />
      {children}
    </Badge>
  )
}
