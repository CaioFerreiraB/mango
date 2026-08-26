import { CalendarIcon } from "lucide-react"
import { useState } from "react"
import type { DateRange } from "react-day-picker"

import { Button } from "@/components/ui/button"
import { Calendar } from "@/components/ui/calendar"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { formatDate } from "@/lib/format"

// Período trafega como `yyyy-mm-dd`; o Calendar trabalha com Date local. Ancorar ao meio-dia
// local evita o dia "virar" na conversão.
function isoParaData(iso: string): Date {
  return new Date(`${iso}T12:00:00`)
}

function dataParaIso(d: Date): string {
  const mes = String(d.getMonth() + 1).padStart(2, "0")
  const dia = String(d.getDate()).padStart(2, "0")
  return `${d.getFullYear()}-${mes}-${dia}`
}

/**
 * Datepicker de intervalo (shadcn) que grava `{inicio, fim}` como `yyyy-mm-dd`. Escolhe as duas
 * datas em rascunho e só confirma no "Aplicar" — não fecha no primeiro clique.
 */
export function PeriodoPicker({
  inicio,
  fim,
  onChange,
}: {
  inicio: string
  fim: string
  onChange: (inicio: string, fim: string) => void
}) {
  const [aberto, setAberto] = useState(false)
  const [rascunho, setRascunho] = useState<DateRange>()

  function aplicar() {
    if (rascunho?.from && rascunho.to) {
      onChange(dataParaIso(rascunho.from), dataParaIso(rascunho.to))
      setAberto(false)
    }
  }

  return (
    <Popover
      open={aberto}
      onOpenChange={(o) => {
        // Semeia o rascunho com o período atual ao abrir.
        if (o) setRascunho({ from: isoParaData(inicio), to: isoParaData(fim) })
        setAberto(o)
      }}
    >
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" className="gap-2">
          <CalendarIcon className="size-4" aria-hidden />
          <span className="tabular-nums">
            {formatDate(inicio)} – {formatDate(fim)}
          </span>
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0" align="end">
        <Calendar
          mode="range"
          numberOfMonths={2}
          defaultMonth={rascunho?.from ?? isoParaData(inicio)}
          selected={rascunho}
          onSelect={(r) => setRascunho(r)}
        />
        <div className="flex items-center justify-between gap-3 border-t p-3">
          <span className="text-xs text-muted-foreground tabular-nums">
            {rascunho?.from ? formatDate(dataParaIso(rascunho.from)) : "Início"}{" "}
            – {rascunho?.to ? formatDate(dataParaIso(rascunho.to)) : "Fim"}
          </span>
          <Button
            size="sm"
            disabled={!rascunho?.from || !rascunho.to}
            onClick={aplicar}
          >
            Aplicar
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  )
}
