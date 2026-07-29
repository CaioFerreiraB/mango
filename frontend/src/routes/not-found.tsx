import { Compass } from "lucide-react"
import { Link } from "react-router"

import { EmptyState } from "@/components/common/empty-state"
import { Button } from "@/components/ui/button"

export function NotFoundPage() {
  return (
    <EmptyState
      icon={Compass}
      title="Página não encontrada"
      description="O endereço acessado não existe ou foi movido."
    >
      <Button asChild>
        <Link to="/">Voltar ao início</Link>
      </Button>
    </EmptyState>
  )
}
