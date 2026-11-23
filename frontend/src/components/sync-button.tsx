import { RefreshCw } from "lucide-react"

import { useSincronizarTudo } from "@/lib/api/conexoes"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

/** "Atualizar conexões" (§4.3): dispara o sync de todos os itens e realimenta um toast. */
export function SyncButton({
  size = "sm",
  compacto = false,
}: {
  size?: "sm" | "default"
  /** Só o ícone em telas pequenas (o rótulo fica para leitor de tela). */
  compacto?: boolean
}) {
  const sync = useSincronizarTudo()
  return (
    <Button
      variant="outline"
      size={size}
      onClick={() => sync.mutate()}
      disabled={sync.isPending}
    >
      <RefreshCw
        className={cn("size-4", sync.isPending && "animate-spin")}
        aria-hidden
      />
      <span className={compacto ? "max-sm:sr-only" : undefined}>
        {sync.isPending ? "Atualizando…" : "Atualizar"}
      </span>
    </Button>
  )
}
