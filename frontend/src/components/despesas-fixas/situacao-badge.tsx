import { Badge } from "@/components/ui/badge"
import {
  estiloSituacao,
  type Situacao,
} from "@/components/despesas-fixas/situacao"
import { cn } from "@/lib/utils"

/** Bolinha + texto: cor nunca é o único sinal (mesmo padrão do `StatusBadge` de revisão). */
export function SituacaoBadge({
  situacao,
  className,
}: {
  situacao: Situacao
  className?: string
}) {
  const { texto, badge, ponto } = estiloSituacao(situacao)
  return (
    <Badge
      variant="secondary"
      className={cn("gap-1.5 font-medium", badge, className)}
    >
      <span className={cn("size-1.5 rounded-full", ponto)} aria-hidden />
      {texto}
    </Badge>
  )
}
