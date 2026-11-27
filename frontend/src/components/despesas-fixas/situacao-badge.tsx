import { Selo } from "@/components/common/selo"
import {
  estiloSituacao,
  type Situacao,
} from "@/components/despesas-fixas/situacao"

export function SituacaoBadge({
  situacao,
  className,
}: {
  situacao: Situacao
  className?: string
}) {
  const { texto, tom } = estiloSituacao(situacao)
  return (
    <Selo tom={tom} className={className}>
      {texto}
    </Selo>
  )
}
