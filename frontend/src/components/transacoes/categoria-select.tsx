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
import { iconeCategoria } from "@/lib/api/categoria-icones"
import { nomeCategoria, useCategorias } from "@/lib/api/categorias"
import { cn } from "@/lib/utils"

/** Seletor da taxonomia do Pluggy. `incluirTodas` adiciona a opção "Todas" (para filtro).
 * `excluir` esconde ids da lista (ex.: categorias já adicionadas em outro lugar). */
export function CategoriaSelect({
  value,
  onChange,
  incluirTodas = false,
  placeholder = "Categoria",
  className,
  excluir,
}: {
  value: string | null
  onChange: (v: string | null) => void
  incluirTodas?: boolean
  placeholder?: string
  className?: string
  excluir?: string[]
}) {
  const { data } = useCategorias()
  const [aberto, setAberto] = useState(false)
  const categorias = (data ?? []).filter((c) => !excluir?.includes(c.pluggy_id))

  const selecionada = value ? categorias.find((c) => c.pluggy_id === value) : null
  const rotulo = selecionada
    ? nomeCategoria(selecionada)
    : incluirTodas && value === null
      ? "Todas as categorias"
      : placeholder

  function selecionar(v: string | null) {
    onChange(v)
    setAberto(false)
  }

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
          <span className="flex min-w-0 items-center gap-2">
            {selecionada
              ? (() => {
                  const Icone = iconeCategoria(selecionada.pluggy_id)
                  return <Icone className="size-4 shrink-0" aria-hidden />
                })()
              : null}
            <span className={cn("truncate", !selecionada && !(incluirTodas && value === null) && "text-muted-foreground")}>
              {rotulo}
            </span>
          </span>
          <ChevronsUpDown className="size-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[var(--radix-popover-trigger-width)] p-0" align="start">
        <Command>
          <CommandInput placeholder="Buscar categoria…" />
          <CommandList className="max-h-56">
            <CommandEmpty>Nenhuma categoria.</CommandEmpty>
            <CommandGroup>
              {incluirTodas ? (
                <CommandItem value="Todas as categorias" onSelect={() => selecionar(null)}>
                  <Check className={cn("size-4", value === null ? "opacity-100" : "opacity-0")} />
                  Todas as categorias
                </CommandItem>
              ) : null}
              {categorias.map((c) => {
                const Icone = iconeCategoria(c.pluggy_id)
                return (
                  <CommandItem
                    key={c.pluggy_id}
                    value={nomeCategoria(c)}
                    onSelect={() => selecionar(c.pluggy_id)}
                  >
                    <Check
                      className={cn(
                        "size-4",
                        value === c.pluggy_id ? "opacity-100" : "opacity-0"
                      )}
                    />
                    <Icone className="size-4 shrink-0 text-muted-foreground" aria-hidden />
                    {nomeCategoria(c)}
                  </CommandItem>
                )
              })}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}
