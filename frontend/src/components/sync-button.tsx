import { RefreshCw } from "lucide-react"

import { useSincronizarTudo } from "@/lib/api/conexoes"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

/** "Atualizar conexões" (§4.3): dispara o sync de todos os itens e realimenta um toast. */
export function SyncButton({ size = "sm" }: { size?: "sm" | "default" }) {
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
      {sync.isPending ? "Atualizando…" : "Atualizar"}
    </Button>
  )
}
