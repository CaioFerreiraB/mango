import { Check, ChevronsUpDown } from "lucide-react"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { useAssinaturas } from "@/lib/api/assinaturas"
import { cn } from "@/lib/utils"

/** Seletor de assinatura (ativas + a já vinculada). Usado no drawer p/ vincular uma transação. */
export function AssinaturaSelect({
  value,
  onChange,
  placeholder = "Escolha a assinatura",
  className,
}: {
  value: number | null
  onChange: (v: number) => void
  placeholder?: string
  className?: string
}) {
  const { data } = useAssinaturas()
  const [aberto, setAberto] = useState(false)
  const todas = data ?? []
  const selecionada = value != null ? todas.find((a) => a.id === value) : null
  // Lista as ativas + a atualmente vinculada (mesmo inativa), para o rótulo não sumir.
  const opcoes = todas.filter((a) => a.ativa || a.id === value)

  return (
    <Popover open={aberto} onOpenChange={setAberto}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={aberto}
          size="sm"
          className={cn("w-full justify-between font-normal", className)}
        >
          <span
            className={cn("truncate", !selecionada && "text-muted-foreground")}
          >
            {selecionada?.nome ?? placeholder}
          </span>
          <ChevronsUpDown className="size-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent
        className="w-[var(--radix-popover-trigger-width)] p-0"
        align="start"
      >
        <Command>
          <CommandInput placeholder="Buscar assinatura…" />
          <CommandList className="max-h-56">
            <CommandEmpty>Nenhuma assinatura.</CommandEmpty>
            <CommandGroup>
              {opcoes.map((a) => (
                <CommandItem
                  key={a.id}
                  value={a.nome}
                  onSelect={() => {
                    onChange(a.id)
                    setAberto(false)
                  }}
                >
                  <Check
                    className={cn(
                      "size-4",
                      value === a.id ? "opacity-100" : "opacity-0"
                    )}
                  />
                  {a.nome}
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}
