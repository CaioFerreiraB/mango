import { ChevronRight, SearchX } from "lucide-react"
import { createElement, useMemo, useState } from "react"
import { toast } from "sonner"

import { EmptyState } from "@/components/common/empty-state"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Switch } from "@/components/ui/switch"
import { iconeCategoria } from "@/lib/api/categoria-icones"
import {
  nomeCategoria,
  useAtualizarCategoria,
  type Categoria,
} from "@/lib/api/categorias"
import { normalizarBusca } from "@/lib/texto"

type No = { categoria: Categoria; filhos: Categoria[] }

/** Taxonomia do banco: só ativar/desativar — renomear mudaria a taxonomia de todos (§4.5). */
export function CategoriasPadraoCard({
  categorias,
}: {
  categorias: Categoria[]
}) {
  const [busca, setBusca] = useState("")
  // Uma única mutação para o card inteiro: um `useMutation` por linha criaria ~130 observers
  // inscritos no cache só para renderizar a lista.
  const atualizar = useAtualizarCategoria()
  const alternar = (id: string, ativa: boolean) =>
    atualizar.mutate(
      { id, patch: { ativa } },
      { onError: (err) => toast.error(err.message) }
    )

  const arvore = useMemo(() => montarArvore(categorias), [categorias])
  const visiveis = useMemo(() => filtrar(arvore, busca), [arvore, busca])

  return (
    <Card>
      <CardHeader className="space-y-1.5">
        <CardTitle className="text-base">Categorias do banco</CardTitle>
        <CardDescription>
          Desative as que você não usa e elas somem dos seletores. Transações
          que o banco classificar numa categoria desativada aparecem como
          “Desconhecida” — desativar alcança as subcategorias.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <Input
          value={busca}
          onChange={(e) => {
            setBusca(e.target.value)
          }}
          placeholder="Buscar categoria…"
          aria-label="Buscar categoria"
        />
        {visiveis.length === 0 ? (
          <EmptyState
            icon={SearchX}
            title="Nenhuma categoria encontrada"
            description={`Nada casa com “${busca}”.`}
          />
        ) : (
          <ul className="divide-y">
            {visiveis.map((no) => (
              <NoRaiz
                // Remonta quando a busca liga/desliga: `expandido` é só estado INICIAL, então
                // sem a key trocar a busca não reabriria os nós filtrados.
                key={`${no.categoria.pluggy_id}-${!!busca}`}
                no={no}
                expandido={!!busca}
                onAlternar={alternar}
              />
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}

function NoRaiz({
  no,
  expandido,
  onAlternar,
}: {
  no: No
  expandido: boolean
  onAlternar: (id: string, ativa: boolean) => void
}) {
  const [aberto, setAberto] = useState(expandido)
  return (
    <li>
      <Collapsible open={aberto} onOpenChange={setAberto}>
        <div className="flex items-center gap-2 py-2">
          {no.filhos.length > 0 ? (
            <CollapsibleTrigger
              // `size-8`: 20px (p-0.5 + ícone) ficava abaixo do mínimo de 24px da WCAG 2.5.8.
              className="flex size-8 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-[color,transform] duration-200 ease-out hover:bg-muted hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none data-[state=open]:rotate-90 motion-reduce:transition-none"
              aria-label={`${aberto ? "Recolher" : "Expandir"} ${nomeCategoria(no.categoria)}`}
            >
              <ChevronRight className="size-4" aria-hidden />
            </CollapsibleTrigger>
          ) : (
            <span className="size-8 shrink-0" aria-hidden />
          )}
          <LinhaCategoria categoria={no.categoria} onAlternar={onAlternar} />
        </div>
        <CollapsibleContent>
          <ul className="ml-4 divide-y border-l pl-4">
            {no.filhos.map((f) => (
              <li key={f.pluggy_id} className="py-2">
                <LinhaCategoria categoria={f} onAlternar={onAlternar} />
              </li>
            ))}
          </ul>
        </CollapsibleContent>
      </Collapsible>
    </li>
  )
}

function LinhaCategoria({
  categoria,
  onAlternar,
}: {
  categoria: Categoria
  onAlternar: (id: string, ativa: boolean) => void
}) {
  const nome = nomeCategoria(categoria)

  return (
    <label className="flex min-w-0 flex-1 items-center gap-2 text-sm">
      {createElement(iconeCategoria(categoria.pluggy_id, categoria.icone), {
        className: "size-4 shrink-0 text-muted-foreground",
        "aria-hidden": true,
      })}
      <span className="min-w-0 flex-1 truncate">{nome}</span>
      <Switch
        checked={categoria.ativa}
        aria-label={`${categoria.ativa ? "Desativar" : "Ativar"} ${nome}`}
        onCheckedChange={(ativa) => {
          onAlternar(categoria.pluggy_id, ativa)
        }}
      />
    </label>
  )
}

/** Raízes + descendentes achatados num nível: a taxonomia tem ≤3 níveis e o 3º é raro, então
 *  indentar duas vezes custaria largura sem ajudar a ler. */
function montarArvore(categorias: Categoria[]): No[] {
  const porPai = new Map<string, Categoria[]>()
  for (const c of categorias) {
    if (c.parent_id) {
      const irmaos = porPai.get(c.parent_id) ?? []
      irmaos.push(c)
      porPai.set(c.parent_id, irmaos)
    }
  }
  const descendentes = (id: string): Categoria[] =>
    (porPai.get(id) ?? []).flatMap((f) => [f, ...descendentes(f.pluggy_id)])

  return categorias
    .filter((c) => !c.parent_id)
    .map((c) => ({ categoria: c, filhos: descendentes(c.pluggy_id) }))
}

/** Casa a raiz OU qualquer descendente; quando casa só um filho, a raiz vem com esse filho. */
function filtrar(arvore: No[], busca: string): No[] {
  const termo = normalizarBusca(busca)
  if (!termo) return arvore
  const casa = (c: Categoria) =>
    normalizarBusca(nomeCategoria(c)).includes(termo)

  return arvore.flatMap((no) => {
    if (casa(no.categoria)) return [no]
    const filhos = no.filhos.filter(casa)
    return filhos.length > 0 ? [{ ...no, filhos }] : []
  })
}
