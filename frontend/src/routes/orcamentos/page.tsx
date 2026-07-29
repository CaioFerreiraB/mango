import { ChevronLeft, ChevronRight, PiggyBank, Plus, Trash2 } from "lucide-react"
import { createElement, useState } from "react"
import { toast } from "sonner"

import { CategoriaSelect } from "@/components/transacoes/categoria-select"
import { EmptyState } from "@/components/common/empty-state"
import { Valor } from "@/components/common/valor"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Progress } from "@/components/ui/progress"
import { Skeleton } from "@/components/ui/skeleton"
import { iconeCategoria } from "@/lib/api/categoria-icones"
import { useMapaCategorias } from "@/lib/api/categorias"
import {
  useAtualizarLimiteMensal,
  useConsumoOrcamentos,
  useCriarOrcamento,
  useRemoverOrcamento,
  type OrcamentoConsumoItem,
} from "@/lib/api/orcamentos"
import { formatMesAno, hojeISO } from "@/lib/format"

// Escala de "calor" do consumo — a cor nunca é o único sinal (o % e o badge também informam).
function corAlerta(alerta: number | null): string {
  if (alerta === null) return "bg-primary"
  if (alerta >= 100) return "bg-red-600"
  if (alerta >= 90) return "bg-orange-600"
  if (alerta >= 75) return "bg-orange-500"
  return "bg-yellow-500"
}

function centavos(reais: string): number {
  return Math.round(Number(reais) * 100)
}

export function OrcamentosPage() {
  const hoje = hojeISO()
  const [ano, setAno] = useState(Number(hoje.slice(0, 4)))
  const [mes, setMes] = useState(Number(hoje.slice(5, 7)))
  const consumo = useConsumoOrcamentos(ano, mes)

  function mudarMes(delta: number) {
    const total = (ano * 12 + (mes - 1) + delta)
    setAno(Math.floor(total / 12))
    setMes((total % 12) + 1)
  }

  const rotuloMes = formatMesAno(`${ano}-${String(mes).padStart(2, "0")}-01`)
  const itens = consumo.data?.itens ?? []

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Orçamentos</h1>
          <p className="text-sm text-muted-foreground">
            Limite mensal por categoria, com alertas em 50%, 75%, 90% e 100%.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 rounded-md border p-0.5">
            <Button variant="ghost" size="icon" onClick={() => mudarMes(-1)} aria-label="Mês anterior">
              <ChevronLeft className="size-4" />
            </Button>
            <span className="min-w-36 text-center text-sm font-medium capitalize">{rotuloMes}</span>
            <Button variant="ghost" size="icon" onClick={() => mudarMes(1)} aria-label="Próximo mês">
              <ChevronRight className="size-4" />
            </Button>
          </div>
          <NovoOrcamentoDialog />
        </div>
      </header>

      {consumo.isError ? (
        <EmptyState title="Não foi possível carregar os orçamentos" />
      ) : consumo.isLoading ? (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-20 w-full" />
          ))}
        </div>
      ) : itens.length === 0 ? (
        <EmptyState
          icon={PiggyBank}
          title="Nenhum orçamento neste mês"
          description="Defina um limite de gasto por categoria para acompanhar o consumo e receber alertas."
        >
          <NovoOrcamentoDialog />
        </EmptyState>
      ) : (
        <div className="space-y-3">
          {itens.map((item) => (
            <OrcamentoRow key={item.orcamento_id} item={item} />
          ))}
        </div>
      )}
    </div>
  )
}

function OrcamentoRow({ item }: { item: OrcamentoConsumoItem }) {
  const nomes = useMapaCategorias()
  const nome = nomes.get(item.categoria_id) ?? item.categoria_id

  return (
    <Card>
      <CardContent className="space-y-2 py-4">
        <div className="flex items-center justify-between gap-3">
          <span className="flex min-w-0 items-center gap-2">
            {createElement(iconeCategoria(item.categoria_id), {
              className: "size-4 shrink-0 text-muted-foreground",
              "aria-hidden": true,
            })}
            <span className="truncate font-medium">{nome}</span>
            {item.alerta_atingido !== null ? (
              <Badge variant={item.alerta_atingido >= 100 ? "destructive" : "secondary"}>
                {item.percentual}%
              </Badge>
            ) : null}
          </span>
          <div className="flex shrink-0 items-center gap-1">
            <EditarLimiteDialog item={item} />
            <RemoverOrcamento id={item.orcamento_id} />
          </div>
        </div>
        <Progress value={item.percentual} indicatorClassName={corAlerta(item.alerta_atingido)} />
        <p className="text-sm text-muted-foreground">
          <Valor centavos={item.gasto_centavos} neutro /> de{" "}
          <Valor centavos={item.limite_centavos} neutro /> ({item.percentual}%)
        </p>
      </CardContent>
    </Card>
  )
}

function NovoOrcamentoDialog() {
  const [aberto, setAberto] = useState(false)
  const [categoria, setCategoria] = useState<string | null>(null)
  const [limite, setLimite] = useState("")
  const criar = useCriarOrcamento()

  function salvar(e: React.FormEvent) {
    e.preventDefault()
    if (!categoria || !limite) return
    criar.mutate(
      {
        categoria_id: categoria,
        limite_padrao_centavos: centavos(limite),
        recorrente: true,
        ativo: true,
      },
      {
        onSuccess: () => {
          toast.success("Orçamento criado.")
          setAberto(false)
          setCategoria(null)
          setLimite("")
        },
        onError: (err) => toast.error(err.message),
      }
    )
  }

  return (
    <Dialog open={aberto} onOpenChange={setAberto}>
      <DialogTrigger asChild>
        <Button>
          <Plus className="size-4" /> Novo orçamento
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Novo orçamento</DialogTitle>
        </DialogHeader>
        <form className="space-y-4" onSubmit={salvar}>
          <div className="space-y-1.5">
            <Label>Categoria</Label>
            <CategoriaSelect value={categoria} onChange={setCategoria} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="limite">Limite mensal (R$)</Label>
            <Input
              id="limite"
              type="number"
              min="0"
              step="0.01"
              value={limite}
              onChange={(e) => setLimite(e.target.value)}
              required
            />
          </div>
          <DialogFooter>
            <DialogClose asChild>
              <Button type="button" variant="ghost">
                Cancelar
              </Button>
            </DialogClose>
            <Button type="submit" disabled={!categoria || !limite || criar.isPending}>
              Criar
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function EditarLimiteDialog({ item }: { item: OrcamentoConsumoItem }) {
  const [aberto, setAberto] = useState(false)
  const [limite, setLimite] = useState(String(item.limite_centavos / 100))
  const atualizar = useAtualizarLimiteMensal()

  function salvar(e: React.FormEvent) {
    e.preventDefault()
    atualizar.mutate(
      { id: item.orcamento_mensal_id, limite_centavos: centavos(limite) },
      {
        onSuccess: () => {
          toast.success("Limite do mês atualizado.")
          setAberto(false)
        },
        onError: (err) => toast.error(err.message),
      }
    )
  }

  return (
    <Dialog open={aberto} onOpenChange={setAberto}>
      <DialogTrigger asChild>
        <Button variant="ghost" size="sm">
          Editar
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Limite do mês</DialogTitle>
        </DialogHeader>
        <form className="space-y-4" onSubmit={salvar}>
          <div className="space-y-1.5">
            <Label htmlFor="limite-mes">Limite (R$)</Label>
            <Input
              id="limite-mes"
              type="number"
              min="0"
              step="0.01"
              value={limite}
              onChange={(e) => setLimite(e.target.value)}
              required
            />
          </div>
          <DialogFooter>
            <DialogClose asChild>
              <Button type="button" variant="ghost">
                Cancelar
              </Button>
            </DialogClose>
            <Button type="submit" disabled={atualizar.isPending}>
              Salvar
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function RemoverOrcamento({ id }: { id: number }) {
  const remover = useRemoverOrcamento()
  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label="Remover orçamento"
      disabled={remover.isPending}
      onClick={() =>
        remover.mutate(id, {
          onSuccess: () => toast.success("Orçamento removido."),
          onError: (err) => toast.error(err.message),
        })
      }
    >
      <Trash2 className="size-4" />
    </Button>
  )
}
