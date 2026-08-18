import { Ban, Check } from "lucide-react"

import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command"
import {
  useConnectoresPluggy,
  useConnectoresSetup,
  type Connector,
} from "@/lib/api/instituicoes"
import { cn } from "@/lib/utils"

/** Seletor de instituição a partir do catálogo do Pluggy (`/connectors`). Filtro client-side pelo
 * nome (o cmdk filtra pelo `value`). ponytail: catálogo carregado inteiro — se ficar grande demais,
 * migrar para busca server-side (`?nome=`). `value` é o `pluggy_connector_id` atual (ou null).
 * `fonte="setup"` troca o endpoint protegido pelo gêmeo público do wizard (sem sessão ainda). */
export function InstituicaoSelect({
  value,
  onChange,
  enabled = true,
  fonte = "app",
}: {
  value: number | null
  onChange: (c: Connector | null) => void
  enabled?: boolean
  fonte?: "app" | "setup"
}) {
  const doApp = useConnectoresPluggy(enabled && fonte === "app")
  const doSetup = useConnectoresSetup(enabled && fonte === "setup")
  const { data, isLoading, isError } = fonte === "setup" ? doSetup : doApp
  const connectores = data ?? []

  return (
    <Command>
      <CommandInput placeholder="Buscar instituição…" />
      <CommandList className="max-h-72">
        <CommandEmpty>
          {isLoading
            ? "Carregando instituições…"
            : isError
              ? "Não foi possível carregar as instituições do Pluggy."
              : "Nenhuma instituição encontrada."}
        </CommandEmpty>
        <CommandGroup>
          <CommandItem value="Sem vínculo manual" onSelect={() => onChange(null)}>
            <Check
              className={cn("size-4", value === null ? "opacity-100" : "opacity-0")}
            />
            <Ban className="size-4 shrink-0 text-muted-foreground" aria-hidden />
            Sem vínculo manual
          </CommandItem>
          {connectores.map((c) => (
            <CommandItem
              key={c.pluggy_connector_id}
              value={`${c.nome} ${c.pluggy_connector_id}`}
              onSelect={() => onChange(c)}
            >
              <Check
                className={cn(
                  "size-4",
                  value === c.pluggy_connector_id ? "opacity-100" : "opacity-0"
                )}
              />
              {c.logo_url ? (
                <img
                  src={c.logo_url}
                  alt=""
                  aria-hidden
                  className="size-5 shrink-0 rounded-sm bg-white object-contain"
                />
              ) : (
                <span className="size-5 shrink-0" aria-hidden />
              )}
              <span className="truncate">{c.nome}</span>
            </CommandItem>
          ))}
        </CommandGroup>
      </CommandList>
    </Command>
  )
}
