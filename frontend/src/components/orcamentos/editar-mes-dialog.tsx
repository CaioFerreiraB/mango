import { Pencil, RotateCcw, Trash2 } from "lucide-react"
import { createElement, useState, type ReactNode } from "react"
import { toast } from "sonner"

import { CurrencyInput } from "@/components/common/currency-input"
import { Valor } from "@/components/common/valor"
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
import { useIsMobile } from "@/hooks/use-mobile"
import { useIconeCategoria } from "@/lib/api/categoria-icones"
import { useMapaCategorias } from "@/lib/api/categorias"
import {
  useAtualizarLimiteMensal,
  useCriarLimiteMensal,
  useCriarOrcamento,
  useRemoverOrcamento,
  type OrcamentoConsumoItem,
} from "@/lib/api/orcamentos"

type Tipo = "despesa" | "receita"

type Nova = { categoriaId: string; tipo: Tipo; valor: number }

const SECOES: { tipo: Tipo; titulo: string }[] = [
  { tipo: "despesa", titulo: "Despesas" },
  { tipo: "receita", titulo: "Receitas" },
]

/** Edição do orçamento **do mês exibido** — limite, adicionar e remover categorias, sem tocar
 *  no orçamento padrão (`ConfigurarOrcamentoPadraoDialog` é o lugar certo pra isso). Remover
 *  uma categoria do padrão só suprime a linha deste mês (`suprimido`, restaurável); uma
 *  categoria adicionada aqui vira um orçamento pontual (`recorrente=false`), restrito a este
 *  mês, e remover de fato apaga. */
export function EditarMesDialog({
  itens,
  ano,
  mes,
  trigger,
  disabled = false,
}: {
  itens: OrcamentoConsumoItem[]
  ano: number
  mes: number
  trigger?: ReactNode
  disabled?: boolean
}) {
  const [aberto, setAberto] = useState(false)
  const [edits, setEdits] = useState<Record<number, number>>({}) // orcamento_mensal_id -> centavos
  const [novas, setNovas] = useState<Record<Tipo, Nova[]>>({
    despesa: [],
    receita: [],
  })
  const [erros, setErros] = useState<Record<string, string>>({})
  const [salvando, setSalvando] = useState(false)
  const nomes = useMapaCategorias()
  const isMobile = useIsMobile()
  const iconeCategoria = useIconeCategoria()

  const atualizarMensal = useAtualizarLimiteMensal()
  const criarOrcamento = useCriarOrcamento()
  const criarLimiteMensal = useCriarLimiteMensal()
  const remover = useRemoverOrcamento()

  function abrir(novoAberto: boolean) {
    setAberto(novoAberto)
    if (novoAberto) {
      setEdits({})
      setNovas({ despesa: [], receita: [] })
      setErros({})
    }
  }

  function adicionarCategoria(tipo: Tipo, categoriaId: string) {
    setNovas((prev) => ({
      ...prev,
      [tipo]: [...prev[tipo], { categoriaId, tipo, valor: 0 }],
    }))
  }

  function mudarValorNova(tipo: Tipo, categoriaId: string, valor: number) {
    setNovas((prev) => ({
      ...prev,
      [tipo]: prev[tipo].map((n) =>
        n.categoriaId === categoriaId ? { ...n, valor } : n
      ),
    }))
  }

  function removerNova(tipo: Tipo, categoriaId: string) {
    setNovas((prev) => ({
      ...prev,
      [tipo]: prev[tipo].filter((n) => n.categoriaId !== categoriaId),
    }))
  }

  /** Remoção é imediata (não fica pendurada até "Salvar"), como o resto do app já faz. Uma
   *  categoria do padrão só é suprimida deste mês; uma pontual é apagada de vez. */
  function removerAtiva(item: OrcamentoConsumoItem) {
    if (item.recorrente) {
      atualizarMensal.mutate(
        { id: item.orcamento_mensal_id, suprimido: true },
        {
          onSuccess: () => toast.success("Categoria removida deste mês."),
          onError: (err) => toast.error(err.message),
        }
      )
    } else {
      remover.mutate(item.orcamento_id, {
        onSuccess: () => toast.success("Orçamento removido."),
        onError: (err) => toast.error(err.message),
      })
    }
  }

  function restaurar(item: OrcamentoConsumoItem) {
    atualizarMensal.mutate(
      { id: item.orcamento_mensal_id, suprimido: false },
      {
        onSuccess: () => toast.success("Categoria restaurada."),
        onError: (err) => toast.error(err.message),
      }
    )
  }

  async function salvar() {
    setSalvando(true)
    const novosErros: Record<string, string> = {}
    let sucessos = 0

    for (const [idStr, valor] of Object.entries(edits)) {
      const id = Number(idStr)
      const item = itens.find((i) => i.orcamento_mensal_id === id)
      if (item && valor === item.limite_centavos) continue
      try {
        await atualizarMensal.mutateAsync({ id, limite_centavos: valor })
        sucessos++
      } catch (err) {
        novosErros[idStr] =
          err instanceof Error ? err.message : "falha ao salvar"
      }
    }

    for (const { tipo } of SECOES) {
      for (const nova of novas[tipo]) {
        const chave = `novo:${tipo}:${nova.categoriaId}`
        try {
          const orc = await criarOrcamento.mutateAsync({
            categoria_id: nova.categoriaId,
            tipo,
            limite_padrao_centavos: nova.valor,
            recorrente: false, // pontual: restrito a este mês, não repete nos seguintes
            ativo: true,
          })
          await criarLimiteMensal.mutateAsync({
            orcamento_id: orc.id,
            categoria_id: nova.categoriaId,
            tipo,
            ano,
            mes,
            limite_centavos: nova.valor,
            editado_manualmente: true,
          })
          sucessos++
        } catch (err) {
          novosErros[chave] =
            err instanceof Error ? err.message : "falha ao salvar"
        }
      }
    }

    setSalvando(false)
    const erroCount = Object.keys(novosErros).length
    if (erroCount === 0) {
      if (sucessos > 0) toast.success("Orçamento do mês atualizado.")
      abrir(false)
    } else {
      setErros(novosErros)
      toast.error(
        sucessos > 0
          ? `${sucessos} alteração(ões) salva(s), ${erroCount} com erro.`
          : `Não foi possível salvar (${erroCount} erro(s)).`
      )
    }
  }

  const houveMudancas =
    Object.keys(edits).length > 0 ||
    novas.despesa.length > 0 ||
    novas.receita.length > 0

  return (
    <Dialog open={aberto} onOpenChange={abrir}>
      <DialogTrigger asChild>
        {trigger ?? (
          <Button variant="outline" disabled={disabled}>
            <Pencil className="size-4" /> Editar mês
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Orçamento do mês</DialogTitle>
          <DialogDescription>
            Vale só pra este mês — o orçamento padrão não muda (edite-o em
            "Configurar orçamento padrão").
          </DialogDescription>
        </DialogHeader>
        <div className="max-h-[60vh] space-y-6 overflow-y-auto pr-1">
          {SECOES.map(({ tipo, titulo }) => {
            const ativos = itens.filter((i) => i.tipo === tipo && !i.suprimido)
            const suprimidos = itens.filter(
              (i) => i.tipo === tipo && i.suprimido
            )
            const excluir = [
              ...itens
                .filter((i) => i.tipo === tipo)
                .map((i) => i.categoria_id),
              ...novas[tipo].map((n) => n.categoriaId),
            ]
            if (
              ativos.length === 0 &&
              suprimidos.length === 0 &&
              novas[tipo].length === 0
            ) {
              return (
                <section key={tipo} className="space-y-2">
                  <h3 className="text-sm font-semibold">{titulo}</h3>
                  <CategoriaSelect
                    value={null}
                    onChange={(id) => id && adicionarCategoria(tipo, id)}
                    excluir={excluir}
                    placeholder="+ Adicionar categoria"
                  />
                </section>
              )
            }
            return (
              <section key={tipo} className="space-y-2">
                <h3 className="text-sm font-semibold">{titulo}</h3>
                <div className="space-y-1">
                  {ativos.map((item) => {
                    const nome =
                      nomes.get(item.categoria_id) ?? item.categoria_id
                    const valor =
                      edits[item.orcamento_mensal_id] ?? item.limite_centavos
                    return (
                      <div key={item.orcamento_mensal_id}>
                        <div className="flex items-center gap-2 py-1">
                          {createElement(iconeCategoria(item.categoria_id), {
                            className: "size-4 shrink-0 text-muted-foreground",
                            "aria-hidden": true,
                          })}
                          {isMobile ? (
                            <div className="min-w-0 flex-1">
                              <p className="truncate text-sm">{nome}</p>
                              <p className="truncate text-xs text-muted-foreground">
                                Gasto:{" "}
                                <Valor
                                  centavos={item.realizado_centavos}
                                  neutro
                                  className="text-xs font-normal"
                                />
                              </p>
                            </div>
                          ) : (
                            <span className="min-w-0 flex-1 truncate text-sm">
                              {nome}
                            </span>
                          )}
                          <CurrencyInput
                            value={valor}
                            onChange={(v) =>
                              setEdits((prev) => ({
                                ...prev,
                                [item.orcamento_mensal_id]: v,
                              }))
                            }
                            className="w-28 shrink-0 sm:w-32"
                            aria-label={`Limite de ${nome}`}
                          />
                          <Button
                            variant="ghost"
                            size="icon"
                            aria-label={`Remover ${nome} deste mês`}
                            onClick={() => removerAtiva(item)}
                          >
                            <Trash2 className="size-4" />
                          </Button>
                        </div>
                        {erros[String(item.orcamento_mensal_id)] ? (
                          <p className="pb-1 pl-6 text-xs text-destructive">
                            {erros[String(item.orcamento_mensal_id)]}
                          </p>
                        ) : null}
                      </div>
                    )
                  })}
                  {novas[tipo].map((nova) => {
                    const nome = nomes.get(nova.categoriaId) ?? nova.categoriaId
                    const chave = `novo:${tipo}:${nova.categoriaId}`
                    return (
                      <div key={nova.categoriaId}>
                        <div className="flex items-center gap-2 py-1">
                          {createElement(iconeCategoria(nova.categoriaId), {
                            className: "size-4 shrink-0 text-muted-foreground",
                            "aria-hidden": true,
                          })}
                          <span className="min-w-0 flex-1 truncate text-sm">
                            {nome}
                          </span>
                          <CurrencyInput
                            value={nova.valor}
                            onChange={(v) =>
                              mudarValorNova(tipo, nova.categoriaId, v)
                            }
                            className="w-28 shrink-0 sm:w-32"
                            aria-label={`Valor de ${nome}`}
                          />
                          <Button
                            variant="ghost"
                            size="icon"
                            aria-label={`Remover ${nome}`}
                            onClick={() => removerNova(tipo, nova.categoriaId)}
                          >
                            <Trash2 className="size-4" />
                          </Button>
                        </div>
                        {erros[chave] ? (
                          <p className="pb-1 pl-6 text-xs text-destructive">
                            {erros[chave]}
                          </p>
                        ) : null}
                      </div>
                    )
                  })}
                  {suprimidos.map((item) => {
                    const nome =
                      nomes.get(item.categoria_id) ?? item.categoria_id
                    return (
                      <div
                        key={item.orcamento_mensal_id}
                        className="flex items-center gap-2 py-1 text-muted-foreground"
                      >
                        {createElement(iconeCategoria(item.categoria_id), {
                          className: "size-4 shrink-0",
                          "aria-hidden": true,
                        })}
                        <span className="min-w-0 flex-1 truncate text-sm line-through">
                          {nome}
                        </span>
                        <span className="text-xs">Removida este mês</span>
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={`Restaurar ${nome}`}
                          onClick={() => restaurar(item)}
                        >
                          <RotateCcw className="size-4" />
                        </Button>
                      </div>
                    )
                  })}
                </div>
                <CategoriaSelect
                  value={null}
                  onChange={(id) => id && adicionarCategoria(tipo, id)}
                  excluir={excluir}
                  placeholder="+ Adicionar categoria"
                />
              </section>
            )
          })}
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
            disabled={salvando || !houveMudancas}
          >
            Salvar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
