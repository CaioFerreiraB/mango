import { createElement } from "react"

import { Button } from "@/components/ui/button"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { ICONES_DISPONIVEIS, iconeCategoria } from "@/lib/api/categoria-icones"
import type { IconeCategoria } from "@/lib/api/categorias"
import { cn } from "@/lib/utils"

/** Escolha do ícone de uma categoria personalizada (§4.5).
 *
 * Grade de botões, e não um `Select`: são ~44 opções sem rótulo útil, e reconhecer o desenho é
 * mais rápido do que ler "utensils-crossed" numa lista vertical. O gatilho mostra o ícone atual,
 * que é o próprio rótulo do campo.
 */
export function IconeSelect({
  value,
  onChange,
  nomeCategoria,
  className,
}: {
  value: IconeCategoria | null | undefined
  onChange: (v: IconeCategoria) => void
  /** Entra no `aria-label` — numa lista de categorias há um destes por linha. */
  nomeCategoria?: string
  className?: string
}) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          size="icon"
          aria-label={
            nomeCategoria ? `Ícone de ${nomeCategoria}` : "Escolher ícone"
          }
          className={cn("shrink-0", className)}
        >
          {/* `createElement`: o ícone sai de um valor em runtime, e ligá-lo a uma variável
              maiúscula no corpo do componente faz o lint entender que nasce um componente novo a
              cada render. O id "u" é qualquer id personalizado — só desvia da taxonomia do Pluggy
              para que `value` (ou o `Tag` padrão) decida. */}
          {createElement(iconeCategoria("u", value), {
            className: "size-4",
            "aria-hidden": true,
          })}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-64 p-2">
        <div
          role="listbox"
          aria-label="Ícones disponíveis"
          className="grid grid-cols-7 gap-1"
        >
          {Object.entries(ICONES_DISPONIVEIS).map(([nome, Icone]) => {
            const selecionado = nome === value
            return (
              <button
                key={nome}
                type="button"
                role="option"
                aria-selected={selecionado}
                aria-label={nome}
                title={nome}
                onClick={() => onChange(nome as IconeCategoria)}
                className={cn(
                  "grid size-8 place-items-center rounded-md text-muted-foreground transition-colors",
                  "hover:bg-accent hover:text-accent-foreground",
                  "focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none",
                  selecionado && "bg-primary text-primary-foreground"
                )}
              >
                {createElement(Icone, {
                  className: "size-4",
                  "aria-hidden": true,
                })}
              </button>
            )
          })}
        </div>
      </PopoverContent>
    </Popover>
  )
}
