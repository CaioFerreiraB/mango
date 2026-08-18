import { Check, ChevronsUpDown, X } from "lucide-react"
import { useState } from "react"

import { PessoaAvatar } from "@/components/divisoes/pessoa-avatar"
import type { PessoaSelecionada } from "@/components/divisoes/pessoa-multi-picker"
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
import { useBuscarUsuarios } from "@/lib/api/usuarios"
import { cn } from "@/lib/utils"

/** Seletor de 1 pessoa da instância (§4.11) — "quem pagou" / "quem deve" no modo integral.
 *  Mesmo padrão de combobox do `CategoriaSelect`, buscando via `/api/usuarios/buscar`.
 *
 *  `value` é o objeto completo (não só o id): a busca de pessoas exclui sempre quem está logado
 *  (`Usuario.id != user.id` no backend — não dá pra "buscar a si mesmo"), então quando o
 *  chamador pré-seleciona o próprio usuário (ex.: default de "com quem" no wizard), o nome/avatar
 *  não podem depender dos resultados da busca — vêm prontos de quem chama, igual ao
 *  `PessoaMultiPicker`. */
export function PessoaSelect({
  value,
  onChange,
  excluir,
  placeholder = "Selecionar pessoa",
  className,
}: {
  value: PessoaSelecionada | null
  onChange: (pessoa: PessoaSelecionada | null) => void
  /** Ids a esconder da lista (ex.: quem já é o pagador, no passo "com quem"). */
  excluir?: number[]
  placeholder?: string
  className?: string
}) {
  const [aberto, setAberto] = useState(false)
  const [busca, setBusca] = useState("")
  const { data, isLoading } = useBuscarUsuarios(busca)
  const pessoas = (data ?? []).filter((p) => !excluir?.includes(p.id))

  return (
    <div className="relative">
      <Popover open={aberto} onOpenChange={setAberto}>
        <PopoverTrigger asChild>
          <Button
            type="button"
            variant="outline"
            role="combobox"
            aria-expanded={aberto}
            className={cn(
              "w-full justify-between font-normal",
              value && "pr-9",
              className
            )}
          >
            <span className="flex min-w-0 items-center gap-2">
              {value ? (
                <PessoaAvatar
                  nome={value.nome}
                  avatar={value.avatar}
                  className="size-5"
                />
              ) : null}
              <span
                className={cn("truncate", !value && "text-muted-foreground")}
              >
                {value?.nome ?? placeholder}
              </span>
            </span>
            <ChevronsUpDown className="size-4 shrink-0 opacity-50" />
          </Button>
        </PopoverTrigger>
        <PopoverContent
          className="w-(--radix-popover-trigger-width) p-0"
          align="start"
        >
          <Command shouldFilter={false}>
            <CommandInput
              placeholder="Buscar pessoa…"
              value={busca}
              onValueChange={setBusca}
            />
            <CommandList className="max-h-56">
              <CommandEmpty>
                {isLoading ? "Buscando…" : "Ninguém encontrado."}
              </CommandEmpty>
              <CommandGroup>
                {pessoas.map((p) => (
                  <CommandItem
                    key={p.id}
                    value={String(p.id)}
                    onSelect={() => {
                      onChange(p)
                      setAberto(false)
                    }}
                  >
                    <Check
                      className={cn(
                        "size-4",
                        value?.id === p.id ? "opacity-100" : "opacity-0"
                      )}
                    />
                    <PessoaAvatar
                      nome={p.nome}
                      avatar={p.avatar}
                      className="size-6"
                    />
                    {p.nome}
                  </CommandItem>
                ))}
              </CommandGroup>
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
      {value ? (
        <button
          type="button"
          aria-label={`Remover ${value.nome}`}
          onClick={() => onChange(null)}
          className="absolute top-1/2 right-8 -translate-y-1/2 rounded-full p-0.5 hover:bg-muted-foreground/20"
        >
          <X className="size-3.5" />
        </button>
      ) : null}
    </div>
  )
}
