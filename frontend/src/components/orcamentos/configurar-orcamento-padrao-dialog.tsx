import {
  DndContext,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core"
import {
  SortableContext,
  arrayMove,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable"
import { CSS } from "@dnd-kit/utilities"
import { GripVertical, Settings2, Trash2 } from "lucide-react"
import { createElement, useState, type ReactNode } from "react"
import { toast } from "sonner"

import { CurrencyInput } from "@/components/common/currency-input"
import { CategoriaSelect } from "@/components/transacoes/categoria-select"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { iconeCategoria } from "@/lib/api/categoria-icones"
import {
  nomeCategoria,
  useCategorias,
  type Categoria,
} from "@/lib/api/categorias"
import {
  useAtualizarOrcamentoPadrao,
  useCriarOrcamento,
  useOrcamentos,
  useRemoverOrcamento,
  type Orcamento,
} from "@/lib/api/orcamentos"

type Tipo = "despesa" | "receita"

type Linha = {
  /** `null` = linha nova, ainda não persistida — só existe no estado local até "Salvar". */
  orcamentoId: number | null
  categoriaId: string
  valor: number // centavos
  ordem: number
}

const SECOES: { tipo: Tipo; titulo: string; vazio: string }[] = [
  {
    tipo: "despesa",
    titulo: "Despesas",
    vazio: "Nenhuma despesa no orçamento padrão ainda.",
  },
  {
    tipo: "receita",
    titulo: "Receitas",
    vazio: "Nenhuma receita no orçamento padrão ainda.",
  },
]

function linhasIniciais(orcamentos: Orcamento[], tipo: Tipo): Linha[] {
  return (
    orcamentos
      // `recorrente=false` são pontuais, criados via "Editar mês" pra um mês específico — não
      // fazem parte do orçamento padrão, então não aparecem aqui.
      .filter((o) => o.tipo === tipo && o.recorrente)
      .sort((a, b) => a.ordem - b.ordem)
      .map((o) => ({
        orcamentoId: o.id,
        categoriaId: o.categoria_id,
        valor: o.limite_padrao_centavos,
        ordem: o.ordem,
      }))
  )
}

/** Modal com duas seções (Despesas/Receitas) pra configurar o orçamento padrão (recorrente) —
 *  só lista categorias já adicionadas, com arrastar-para-reordenar e "+ Adicionar categoria".
 *  Não mexe na linha do mês corrente (`EditarMesDialog` é o lugar certo pra isso). */
export function ConfigurarOrcamentoPadraoDialog({
  trigger,
}: { trigger?: ReactNode } = {}) {
  const [aberto, setAberto] = useState(false)
  const [linhas, setLinhas] = useState<Record<Tipo, Linha[]>>({
    despesa: [],
    receita: [],
  })
  const [erros, setErros] = useState<Record<string, string>>({})
  const [salvando, setSalvando] = useState(false)

  const categorias = useCategorias().data ?? []
  const orcamentos = useOrcamentos().data ?? []
  const original = new Map(orcamentos.map((o) => [o.id, o]))

  const criar = useCriarOrcamento()
  const atualizar = useAtualizarOrcamentoPadrao()
  const remover = useRemoverOrcamento()

  function abrir(novoAberto: boolean) {
    setAberto(novoAberto)
    if (novoAberto) {
      setLinhas({
        despesa: linhasIniciais(orcamentos, "despesa"),
        receita: linhasIniciais(orcamentos, "receita"),
      })
      setErros({})
    }
  }

  function mudarValor(tipo: Tipo, categoriaId: string, centavos: number) {
    setLinhas((prev) => ({
      ...prev,
      [tipo]: prev[tipo].map((l) =>
        l.categoriaId === categoriaId ? { ...l, valor: centavos } : l
      ),
    }))
  }

  function adicionarCategoria(tipo: Tipo, categoriaId: string) {
    setLinhas((prev) => ({
      ...prev,
      [tipo]: [
        ...prev[tipo],
        { orcamentoId: null, categoriaId, valor: 0, ordem: prev[tipo].length },
      ],
    }))
  }

  /** Linha nova (nunca salva): só sai do estado local. Linha existente: remove de verdade —
   *  ação imediata (não fica pendurada até "Salvar"), como o resto do app já faz pra exclusão. */
  function removerLinha(tipo: Tipo, linha: Linha) {
    if (linha.orcamentoId === null) {
      setLinhas((prev) => ({
        ...prev,
        [tipo]: prev[tipo].filter((l) => l !== linha),
      }))
      return
    }
    remover.mutate(linha.orcamentoId, {
      onSuccess: () => {
        toast.success("Orçamento removido.")
        setLinhas((prev) => ({
          ...prev,
          [tipo]: prev[tipo].filter((l) => l !== linha),
        }))
      },
      onError: (err) => toast.error(err.message),
    })
  }

  function arrastarFim(tipo: Tipo, event: DragEndEvent) {
    const { active, over } = event
    if (!over || active.id === over.id) return
    setLinhas((prev) => {
      const lista = prev[tipo]
      const de = lista.findIndex((l) => l.categoriaId === active.id)
      const para = lista.findIndex((l) => l.categoriaId === over.id)
      if (de === -1 || para === -1) return prev
      const reordenada = arrayMove(lista, de, para).map((l, i) => ({
        ...l,
        ordem: i,
      }))
      return { ...prev, [tipo]: reordenada }
    })
  }

  async function salvar() {
    setSalvando(true)
    const novosErros: Record<string, string> = {}
    let sucessos = 0

    for (const { tipo } of SECOES) {
      for (const linha of linhas[tipo]) {
        const chave = `${tipo}:${linha.categoriaId}`
        try {
          if (linha.orcamentoId === null) {
            const criado = await criar.mutateAsync({
              categoria_id: linha.categoriaId,
              tipo,
              limite_padrao_centavos: linha.valor,
              recorrente: true,
              ativo: true,
            })
            if (criado.ordem !== linha.ordem) {
              await atualizar.mutateAsync({ id: criado.id, ordem: linha.ordem })
            }
            sucessos++
          } else {
            const existente = original.get(linha.orcamentoId)
            const patch: { limite_padrao_centavos?: number; ordem?: number } =
              {}
            if (
              !existente ||
              linha.valor !== existente.limite_padrao_centavos
            ) {
              patch.limite_padrao_centavos = linha.valor
            }
            if (!existente || linha.ordem !== existente.ordem) {
              patch.ordem = linha.ordem
            }
            if (Object.keys(patch).length > 0) {
              await atualizar.mutateAsync({ id: linha.orcamentoId, ...patch })
              sucessos++
            }
          }
        } catch (err) {
          novosErros[chave] =
            err instanceof Error ? err.message : "falha ao salvar"
        }
      }
    }

    setSalvando(false)
    const erroCount = Object.keys(novosErros).length
    if (erroCount === 0) {
      if (sucessos > 0) toast.success("Orçamento padrão atualizado.")
      setAberto(false)
    } else {
      setErros(novosErros)
      toast.error(
        sucessos > 0
          ? `${sucessos} alteração(ões) salva(s), ${erroCount} com erro.`
          : `Não foi possível salvar (${erroCount} erro(s)).`
      )
    }
  }

  function houveMudancas(): boolean {
    for (const { tipo } of SECOES) {
      for (const linha of linhas[tipo]) {
        if (linha.orcamentoId === null) return true // linha nova, ainda não salva
        const existente = original.get(linha.orcamentoId)
        if (
          !existente ||
          linha.valor !== existente.limite_padrao_centavos ||
          linha.ordem !== existente.ordem
        ) {
          return true
        }
      }
    }
    const idsAtuais = new Set(
      [...linhas.despesa, ...linhas.receita].map((l) => l.orcamentoId)
    )
    // Alguma linha original (recorrente) foi removida? Pontuais (recorrente=false) não entram
    // aqui — não fazem parte deste modal.
    return orcamentos.some((o) => o.recorrente && !idsAtuais.has(o.id))
  }

  return (
    <Dialog open={aberto} onOpenChange={abrir}>
      <DialogTrigger asChild>
        {trigger ?? (
          <Button>
            <Settings2 className="size-4" /> Configurar orçamento padrão
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Orçamento padrão</DialogTitle>
          <DialogDescription>
            Vale a partir do próximo mês materializado — o mês atual não muda
            automaticamente (use "Editar mês" pra isso).
          </DialogDescription>
        </DialogHeader>
        <div className="max-h-[60vh] space-y-6 overflow-y-auto pr-1">
          {SECOES.map(({ tipo, titulo, vazio }) => (
            <SecaoTipo
              key={tipo}
              tipo={tipo}
              titulo={titulo}
              vazio={vazio}
              linhas={linhas[tipo]}
              categorias={categorias}
              excluir={linhas[tipo].map((l) => l.categoriaId)}
              erros={erros}
              onMudarValor={(categoriaId, v) =>
                mudarValor(tipo, categoriaId, v)
              }
              onRemover={(linha) => removerLinha(tipo, linha)}
              onAdicionar={(categoriaId) =>
                adicionarCategoria(tipo, categoriaId)
              }
              onArrastarFim={(e) => arrastarFim(tipo, e)}
            />
          ))}
        </div>
        <DialogFooter>
          <DialogClose asChild>
            <Button type="button" variant="ghost">
              Cancelar
            </Button>
          </DialogClose>
          <Button
            type="button"
            onClick={salvar}
            disabled={salvando || !houveMudancas()}
          >
            Salvar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function SecaoTipo({
  tipo,
  titulo,
  vazio,
  linhas,
  categorias,
  excluir,
  erros,
  onMudarValor,
  onRemover,
  onAdicionar,
  onArrastarFim,
}: {
  tipo: Tipo
  titulo: string
  vazio: string
  linhas: Linha[]
  categorias: Categoria[]
  excluir: string[]
  erros: Record<string, string>
  onMudarValor: (categoriaId: string, centavos: number) => void
  onRemover: (linha: Linha) => void
  onAdicionar: (categoriaId: string) => void
  onArrastarFim: (event: DragEndEvent) => void
}) {
  const sensores = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } })
  )
  const mapaCategorias = new Map(categorias.map((c) => [c.pluggy_id, c]))

  return (
    <section className="space-y-2">
      <h3 className="text-sm font-semibold">{titulo}</h3>
      {linhas.length === 0 ? (
        <p className="text-sm text-muted-foreground">{vazio}</p>
      ) : (
        <DndContext
          sensors={sensores}
          collisionDetection={closestCenter}
          onDragEnd={onArrastarFim}
        >
          <SortableContext
            items={linhas.map((l) => l.categoriaId)}
            strategy={verticalListSortingStrategy}
          >
            <div className="space-y-1">
              {linhas.map((linha) => {
                const categoria = mapaCategorias.get(linha.categoriaId)
                if (!categoria) return null
                return (
                  <LinhaArrastavel
                    key={linha.categoriaId}
                    linha={linha}
                    nome={nomeCategoria(categoria)}
                    erro={erros[`${tipo}:${linha.categoriaId}`]}
                    onMudarValor={(v) => onMudarValor(linha.categoriaId, v)}
                    onRemover={() => onRemover(linha)}
                  />
                )
              })}
            </div>
          </SortableContext>
        </DndContext>
      )}
      <CategoriaSelect
        value={null}
        onChange={(id) => id && onAdicionar(id)}
        excluir={excluir}
        placeholder="+ Adicionar categoria"
      />
    </section>
  )
}

function LinhaArrastavel({
  linha,
  nome,
  erro,
  onMudarValor,
  onRemover,
}: {
  linha: Linha
  nome: string
  erro: string | undefined
  onMudarValor: (centavos: number) => void
  onRemover: () => void
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({
    id: linha.categoriaId,
  })
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.6 : 1,
  }

  return (
    <div ref={setNodeRef} style={style}>
      <div className="flex items-center gap-2 py-1">
        <button
          type="button"
          className="-m-2 cursor-grab touch-none p-2 text-muted-foreground active:cursor-grabbing"
          aria-label={`Reordenar ${nome}`}
          {...attributes}
          {...listeners}
        >
          <GripVertical className="size-4" />
        </button>
        {createElement(iconeCategoria(linha.categoriaId), {
          className: "size-4 shrink-0 text-muted-foreground",
          "aria-hidden": true,
        })}
        <span className="min-w-0 flex-1 truncate text-sm">{nome}</span>
        <CurrencyInput
          value={linha.valor}
          onChange={onMudarValor}
          className="w-28 shrink-0 sm:w-32"
          aria-label={`Valor de ${nome}`}
        />
        <Button
          variant="ghost"
          size="icon"
          aria-label={`Remover ${nome}`}
          onClick={onRemover}
        >
          <Trash2 className="size-4" />
        </Button>
      </div>
      {erro ? (
        <p className="pb-1 pl-6 text-xs text-destructive">{erro}</p>
      ) : null}
    </div>
  )
}
