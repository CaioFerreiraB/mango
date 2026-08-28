import { Check, ChevronsUpDown } from "lucide-react"
import { createElement, useState } from "react"

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
import {
  nomeCategoria,
  useCategorias,
  type Categoria,
} from "@/lib/api/categorias"
import { cn } from "@/lib/utils"

/** Seletor de categoria (taxonomia do banco + as criadas pelo usuário, §4.5).
 * `incluirTodas` adiciona a opção "Todas" (para filtro); `excluir` esconde ids da lista (ex.:
 * categorias já adicionadas em outro lugar); `disabled` bloqueia a escolha (cobrança de
 * assinatura tem a categoria da assinatura). */
export function CategoriaSelect({
  value,
  onChange,
  incluirTodas = false,
  placeholder = "Categoria",
  className,
  excluir,
  disabled = false,
}: {
  value: string | null
  onChange: (v: string | null) => void
  incluirTodas?: boolean
  placeholder?: string
  className?: string
  excluir?: string[]
  disabled?: boolean
}) {
  const { data } = useCategorias()
  const [aberto, setAberto] = useState(false)
  // Inativas ficam fora das opções — desativar existe justamente para tirá-las da frente. A que
  // já está selecionada continua na lista, senão o valor atual sumiria do seletor.
  const categorias = (data ?? []).filter(
    (c) => !excluir?.includes(c.pluggy_id) && (c.ativa || c.pluggy_id === value)
  )
  const personalizadas = categorias.filter((c) => c.personalizada)
  const doBanco = categorias.filter((c) => !c.personalizada)

  const selecionada = value
    ? categorias.find((c) => c.pluggy_id === value)
    : null
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
    // `modal`: sem isto a lista não rola com roda nem com gesto — só arrastando a barra. O
    // seletor quase sempre abre dentro de um Dialog ou do Drawer de detalhe, e os dois montam um
    // `RemoveScroll` que cancela `wheel`/`touchmove` de qualquer alvo fora do conteúdo deles.
    // Como o popover é portalado para o `body`, ele cai justamente nesse "fora" (arrastar a barra
    // escapava por não emitir esses eventos). `modal` faz o próprio popover empilhar um
    // `RemoveScroll`, e só o último da pilha fica ativo — a lista volta a ser área rolável.
    <Popover open={aberto} onOpenChange={setAberto} modal>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={aberto}
          disabled={disabled}
          size="sm"
          className={cn("w-full justify-between font-normal", className)}
        >
          <span className="flex min-w-0 items-center gap-2">
            {selecionada
              ? (() => {
                  const Icone = iconeCategoria(
                    selecionada.pluggy_id,
                    selecionada.icone
                  )
                  return <Icone className="size-4 shrink-0" aria-hidden />
                })()
              : null}
            <span
              className={cn(
                "truncate",
                !selecionada &&
                  !(incluirTodas && value === null) &&
                  "text-muted-foreground"
              )}
            >
              {rotulo}
            </span>
          </span>
          <ChevronsUpDown className="size-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent
        className="w-[var(--radix-popover-trigger-width)] p-0"
        align="start"
      >
        <Command>
          <CommandInput placeholder="Buscar categoria…" />
          {/* A taxonomia tem ~130 categorias e o `max-h-56` daqui mostrava 6 — o resto só pela
              busca. A barra de rolagem vem do `CommandList` (ver o porquê lá); a altura é o menor
              entre 24rem e o espaço que o Radix mediu até a borda da tela (menos o campo de
              busca), então a lista cresce onde cabe e não estoura em janela baixa nem no celular.
              O fallback do `var()` cobre o caso de o popover renderizar sem medida. */}
          <CommandList className="max-h-[min(24rem,calc(var(--radix-popover-content-available-height,60vh)-4rem))]">
            <CommandEmpty>Nenhuma categoria.</CommandEmpty>
            <CommandGroup>
              {incluirTodas ? (
                <CommandItem
                  value="Todas as categorias"
                  onSelect={() => selecionar(null)}
                >
                  <Check
                    className={cn(
                      "size-4",
                      value === null ? "opacity-100" : "opacity-0"
                    )}
                  />
                  Todas as categorias
                </CommandItem>
              ) : null}
              {doBanco.map((c) => (
                <Item
                  key={c.pluggy_id}
                  categoria={c}
                  selecionado={value === c.pluggy_id}
                  onSelect={selecionar}
                />
              ))}
            </CommandGroup>
            {personalizadas.length > 0 ? (
              <CommandGroup heading="Minhas categorias">
                {personalizadas.map((c) => (
                  <Item
                    key={c.pluggy_id}
                    categoria={c}
                    selecionado={value === c.pluggy_id}
                    onSelect={selecionar}
                  />
                ))}
              </CommandGroup>
            ) : null}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}

function Item({
  categoria,
  selecionado,
  onSelect,
}: {
  categoria: Categoria
  selecionado: boolean
  onSelect: (v: string) => void
}) {
  return (
    <CommandItem
      value={nomeCategoria(categoria)}
      onSelect={() => {
        onSelect(categoria.pluggy_id)
      }}
    >
      <Check
        className={cn("size-4", selecionado ? "opacity-100" : "opacity-0")}
      />
      {/* `createElement`: o ícone é escolhido em runtime pelo id, e ligá-lo a uma variável
          maiúscula no corpo do componente faz o lint entender que um componente novo nasce a
          cada render (mesmo padrão de orcamentos/page.tsx). */}
      {createElement(iconeCategoria(categoria.pluggy_id, categoria.icone), {
        className: "size-4 shrink-0 text-muted-foreground",
        "aria-hidden": true,
      })}
      {nomeCategoria(categoria)}
    </CommandItem>
  )
}
