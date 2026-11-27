import { Selo } from "@/components/common/selo"
import type { TomSelo } from "@/components/common/selo-tons"
import type { EstadoRevisao } from "@/lib/revisao"

const AJUDA_IGNORADA =
  "Anterior à data de início da revisão — não entra na fila. Ajuste em Configurações → Preferências."

/** `switch` exaustivo: o TS garante que nenhum estado fica de fora. */
function estilo(estado: EstadoRevisao): { texto: string; tom: TomSelo } {
  switch (estado) {
    case "revisado":
      return { texto: "Revisado", tom: "sucesso" }
    case "pendente":
      return { texto: "Pendente", tom: "aviso" }
    case "ignorado":
      return { texto: "Ignorada", tom: "apagado" }
  }
}

/** Selo de revisão da transação. */
export function StatusBadge({
  estado,
  className,
}: {
  estado: EstadoRevisao
  className?: string
}) {
  const { texto, tom } = estilo(estado)
  return (
    <Selo
      tom={tom}
      className={className}
      title={estado === "ignorado" ? AJUDA_IGNORADA : undefined}
    >
      {texto}
    </Selo>
  )
}
