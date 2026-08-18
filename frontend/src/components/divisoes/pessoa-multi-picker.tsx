import { Search } from "lucide-react"
import { useState } from "react"

import { PessoaAvatar } from "@/components/divisoes/pessoa-avatar"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { useBuscarUsuarios } from "@/lib/api/usuarios"

export type PessoaSelecionada = {
  id: number
  nome: string
  avatar: number | null
}

/** Seletor de N pessoas (§4.11 — "com quem dividir"): busca + lista única de checkboxes (marcar/
 *  desmarcar é a própria seleção, sem chips duplicando a informação acima). Não existe combobox
 *  multi-select pronto no app (`CategoriaSelect` é single-select via `Command`) — este é o padrão
 *  novo, reaproveitável fora do wizard também. */
export function PessoaMultiPicker({
  value,
  onChange,
  excluir,
  eu,
}: {
  value: PessoaSelecionada[]
  onChange: (pessoas: PessoaSelecionada[]) => void
  /** Ids a esconder da lista de busca (ex.: quem já é o pagador, já contado à parte). */
  excluir?: number[]
  /** Usuário logado, pra aparecer como uma linha normal da lista — a busca
   *  (`/api/usuarios/buscar`) nunca devolve a si mesma, então precisa ser injetada aqui. */
  eu?: PessoaSelecionada | null
}) {
  const [busca, setBusca] = useState("")
  const { data, isLoading } = useBuscarUsuarios(busca)
  const selecionadosIds = new Set(value.map((p) => p.id))
  const resultadosBusca = (data ?? []).filter((p) => !excluir?.includes(p.id))
  const buscaCasaComEu =
    !busca.trim() || eu?.nome.toLowerCase().includes(busca.trim().toLowerCase())
  const resultados: PessoaSelecionada[] =
    eu &&
    buscaCasaComEu &&
    !excluir?.includes(eu.id) &&
    !resultadosBusca.some((p) => p.id === eu.id)
      ? [eu, ...resultadosBusca]
      : resultadosBusca

  function alternar(p: PessoaSelecionada) {
    if (selecionadosIds.has(p.id)) {
      onChange(value.filter((v) => v.id !== p.id))
    } else {
      onChange([...value, { id: p.id, nome: p.nome, avatar: p.avatar }])
    }
  }

  return (
    <div className="space-y-3">
      <div className="relative">
        <Search className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="Buscar pessoas…"
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
          className="pl-8"
        />
      </div>

      <div className="max-h-56 divide-y overflow-y-auto rounded-lg border">
        {isLoading ? (
          <p className="p-3 text-sm text-muted-foreground">Buscando…</p>
        ) : resultados.length === 0 ? (
          <p className="p-3 text-sm text-muted-foreground">
            Ninguém encontrado.
          </p>
        ) : (
          resultados.map((p) => {
            const marcado = selecionadosIds.has(p.id)
            return (
              <label
                key={p.id}
                className="flex cursor-pointer items-center gap-3 p-2.5 hover:bg-muted/50"
              >
                <Checkbox
                  checked={marcado}
                  onCheckedChange={() => alternar(p)}
                />
                <PessoaAvatar
                  nome={p.nome}
                  avatar={p.avatar}
                  className="size-8"
                />
                <span className="min-w-0 flex-1 truncate text-sm">
                  {p.nome}
                </span>
              </label>
            )
          })
        )}
      </div>
    </div>
  )
}
