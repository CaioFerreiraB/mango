import { AlertTriangle } from "lucide-react"
import type { ReactNode } from "react"

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import type { Granularidade } from "@/lib/api/dashboard"

// Molduras comuns às abas do dashboard (Geral, Receitas, Despesas).

export function CardGrafico({
  titulo,
  descricao,
  acao,
  children,
}: {
  titulo: string
  descricao?: string
  acao?: ReactNode
  children: ReactNode
}) {
  return (
    <Card className="min-w-0">
      <CardHeader className="flex-row flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="min-w-0">
          <CardTitle>{titulo}</CardTitle>
          {descricao ? <CardDescription>{descricao}</CardDescription> : null}
        </div>
        {acao}
      </CardHeader>
      <CardContent className="@container">{children}</CardContent>
    </Card>
  )
}

export function ErroCard() {
  return (
    <Card>
      <CardContent className="flex items-center gap-2 text-sm text-muted-foreground">
        <AlertTriangle className="size-4" aria-hidden />
        Não foi possível carregar.
      </CardContent>
    </Card>
  )
}

export function SeletorGranularidade({
  valor,
  onChange,
}: {
  valor: Granularidade
  onChange: (g: Granularidade) => void
}) {
  return (
    <ToggleGroup
      type="single"
      size="sm"
      variant="outline"
      spacing={0}
      value={valor}
      onValueChange={(v) => v && onChange(v as Granularidade)}
    >
      <ToggleGroupItem value="diaria">Diário</ToggleGroupItem>
      <ToggleGroupItem value="semanal">Semanal</ToggleGroupItem>
      <ToggleGroupItem value="mensal">Mensal</ToggleGroupItem>
      <ToggleGroupItem value="anual">Anual</ToggleGroupItem>
    </ToggleGroup>
  )
}

/** Carregando / erro / conteúdo — estados de todo gráfico das abas. */
export function Estado({
  carregando,
  erro,
  altura = "h-[260px]",
  children,
}: {
  carregando: boolean
  erro: boolean
  altura?: string
  children: ReactNode
}) {
  if (carregando) return <Skeleton className={`${altura} w-full`} />
  if (erro)
    return (
      <p className="flex items-center justify-center gap-2 py-8 text-sm text-muted-foreground">
        <AlertTriangle className="size-4" aria-hidden />
        Não foi possível carregar.
      </p>
    )
  return <>{children}</>
}
