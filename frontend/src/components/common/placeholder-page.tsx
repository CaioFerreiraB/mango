import { Construction } from "lucide-react"

import type { LucideIcon } from "lucide-react"

import { EmptyState } from "@/components/common/empty-state"

type PlaceholderPageProps = {
  title: string
  description?: string
  icon?: LucideIcon
}

/**
 * Conteúdo padrão das rotas ainda não implementadas. O esqueleto reserva a rota e a navegação; a
 * tela real entra na fase correspondente do roadmap. Reutilizado por todas as seções de domínio.
 */
export function PlaceholderPage({
  title,
  description,
  icon,
}: PlaceholderPageProps) {
  return (
    <EmptyState
      icon={icon ?? Construction}
      title={`${title} — em construção`}
      description={
        description ??
        "Esta seção faz parte do esqueleto da interface. A implementação chega na fase correspondente."
      }
    />
  )
}
