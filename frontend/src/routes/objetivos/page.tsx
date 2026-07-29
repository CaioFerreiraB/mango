import { Plus, Target, X } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import { EmptyState } from "@/components/common/empty-state"
import { Valor } from "@/components/common/valor"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Textarea } from "@/components/ui/textarea"
import { useContas } from "@/lib/api/contas"
import { useInvestimentos } from "@/lib/api/investimentos"
import {
  useAtualizarObjetivo,
  useCriarObjetivo,
  useObjetivo,
  useObjetivos,
  useRemoverObjetivo,
  useVincularConta,
  useVincularInvestimento,
  type Objetivo,
} from "@/lib/api/objetivos"

const GRID = "grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3"

function centavos(reais: string): number {
  return Math.round(Number(reais) * 100)
}

export function ObjetivosPage() {
  const { data, isLoading, isError } = useObjetivos()
  const [detalhe, setDetalhe] = useState<number | null>(null)

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Objetivos</h1>
          <p className="text-sm text-muted-foreground">
            Metas financeiras alimentadas pelo saldo das contas e investimentos vinculados.
          </p>
        </div>
        <ObjetivoFormDialog
          trigger={
            <Button>
              <Plus className="size-4" /> Novo objetivo
            </Button>
          }
        />
      </header>

      {isError ? (
        <EmptyState title="Não foi possível carregar os objetivos" />
      ) : isLoading ? (
        <div className={GRID}>
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-36 w-full" />
          ))}
        </div>
      ) : (data ?? []).length === 0 ? (
        <EmptyState
          icon={Target}
          title="Nenhum objetivo ainda"
          description="Crie uma meta (viagem, reserva de emergência…) e vincule contas ou investimentos para acompanhar o progresso."
        >
          <ObjetivoFormDialog
            trigger={
              <Button>
                <Plus className="size-4" /> Novo objetivo
              </Button>
            }
          />
        </EmptyState>
      ) : (
        <div className={GRID}>
          {(data ?? []).map((o) => (
            <ObjetivoCard key={o.id} objetivo={o} onAbrir={() => setDetalhe(o.id)} />
          ))}
        </div>
      )}

      {detalhe !== null ? (
        <ObjetivoDetalheDialog id={detalhe} onClose={() => setDetalhe(null)} />
      ) : null}
    </div>
  )
}

function ObjetivoCard({ objetivo, onAbrir }: { objetivo: Objetivo; onAbrir: () => void }) {
  const pct = Math.round(objetivo.progresso * 100)
  return (
    <Card className="cursor-pointer transition-colors hover:border-primary/50" onClick={onAbrir}>
      <CardHeader className="pb-2">
        <p className="font-medium break-words [overflow-wrap:anywhere]">{objetivo.titulo}</p>
        {objetivo.descricao ? (
          <p className="line-clamp-2 text-xs text-muted-foreground">{objetivo.descricao}</p>
        ) : null}
      </CardHeader>
      <CardContent className="space-y-2">
        <Progress value={pct} />
        <div className="flex items-baseline justify-between text-sm">
          <Valor centavos={objetivo.valor_guardado_centavos} neutro className="text-base" />
          <span className="text-muted-foreground">
            de <Valor centavos={objetivo.valor_alvo_centavos} neutro /> ({pct}%)
          </span>
        </div>
      </CardContent>
    </Card>
  )
}

function ObjetivoFormDialog({
  trigger,
  objetivo,
}: {
  trigger: React.ReactNode
  objetivo?: Objetivo
}) {
  const [aberto, setAberto] = useState(false)
  const [form, setForm] = useState({
    titulo: objetivo?.titulo ?? "",
    descricao: objetivo?.descricao ?? "",
    justificativa: objetivo?.justificativa ?? "",
    alvo: objetivo ? String(objetivo.valor_alvo_centavos / 100) : "",
  })
  const criar = useCriarObjetivo()
  const atualizar = useAtualizarObjetivo()
  const pendente = criar.isPending || atualizar.isPending

  function salvar(e: React.FormEvent) {
    e.preventDefault()
    const body = {
      titulo: form.titulo,
      descricao: form.descricao || null,
      justificativa: form.justificativa || null,
      valor_alvo_centavos: centavos(form.alvo),
    }
    const onSuccess = () => {
      toast.success(objetivo ? "Objetivo atualizado." : "Objetivo criado.")
      setAberto(false)
    }
    const onError = (err: Error) => toast.error(err.message)
    if (objetivo) atualizar.mutate({ id: objetivo.id, patch: body }, { onSuccess, onError })
    else criar.mutate(body, { onSuccess, onError })
  }

  return (
    <Dialog open={aberto} onOpenChange={setAberto}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{objetivo ? "Editar objetivo" : "Novo objetivo"}</DialogTitle>
        </DialogHeader>
        <form className="space-y-4" onSubmit={salvar}>
          <div className="space-y-1.5">
            <Label htmlFor="titulo">Título</Label>
            <Input
              id="titulo"
              value={form.titulo}
              onChange={(e) => setForm({ ...form, titulo: e.target.value })}
              required
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="alvo">Valor-alvo (R$)</Label>
            <Input
              id="alvo"
              type="number"
              min="0"
              step="0.01"
              value={form.alvo}
              onChange={(e) => setForm({ ...form, alvo: e.target.value })}
              required
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="descricao">Descrição</Label>
            <Textarea
              id="descricao"
              value={form.descricao}
              onChange={(e) => setForm({ ...form, descricao: e.target.value })}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="justificativa">Justificativa</Label>
            <Textarea
              id="justificativa"
              value={form.justificativa}
              onChange={(e) => setForm({ ...form, justificativa: e.target.value })}
            />
          </div>
          <DialogFooter>
            <DialogClose asChild>
              <Button type="button" variant="ghost">
                Cancelar
              </Button>
            </DialogClose>
            <Button type="submit" disabled={!form.titulo || !form.alvo || pendente}>
              Salvar
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function ObjetivoDetalheDialog({ id, onClose }: { id: number; onClose: () => void }) {
  const { data, isLoading } = useObjetivo(id)
  const contas = useContas()
  const investimentos = useInvestimentos()
  const vincularConta = useVincularConta()
  const vincularInv = useVincularInvestimento()
  const remover = useRemoverObjetivo()

  // Disponíveis para vincular = sem objetivo (a regra 1:1-máx impede roubar de outro objetivo).
  const contasLivres = (contas.data ?? []).filter((c) => c.objetivo_id == null)
  const invsLivres = (investimentos.data ?? []).filter((i) => i.objetivo_id == null)

  function adicionar(valor: string) {
    const [tipo, idStr] = valor.split(":")
    const alvoId = Number(idStr)
    const onError = (err: Error) => toast.error(err.message)
    if (tipo === "conta") vincularConta.mutate({ contaId: alvoId, objetivoId: id }, { onError })
    else vincularInv.mutate({ investimentoId: alvoId, objetivoId: id }, { onError })
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        {isLoading || !data ? (
          <Skeleton className="h-48 w-full" />
        ) : (
          <>
            <DialogHeader>
              <DialogTitle>{data.titulo}</DialogTitle>
            </DialogHeader>

            <div className="space-y-3">
              <Progress value={Math.round(data.progresso * 100)} />
              <p className="text-sm text-muted-foreground">
                <Valor centavos={data.valor_guardado_centavos} neutro /> de{" "}
                <Valor centavos={data.valor_alvo_centavos} neutro /> guardados (
                {Math.round(data.progresso * 100)}%)
              </p>
              {data.justificativa ? (
                <p className="text-sm text-muted-foreground">{data.justificativa}</p>
              ) : null}

              <div className="space-y-2">
                <Label className="text-xs text-muted-foreground">Contas e investimentos</Label>
                {data.vinculos.length === 0 ? (
                  <p className="text-sm text-muted-foreground">Nenhum vínculo ainda.</p>
                ) : (
                  <ul className="space-y-1.5">
                    {data.vinculos.map((v) => (
                      <li
                        key={`${v.tipo}-${v.id}`}
                        className="flex items-center justify-between gap-2 rounded-md border px-3 py-2 text-sm"
                      >
                        <span className="min-w-0 truncate">
                          {v.nome ?? (v.tipo === "conta" ? "Conta" : "Investimento")}
                          <span className="ml-2 text-xs text-muted-foreground capitalize">
                            {v.tipo}
                          </span>
                        </span>
                        <span className="flex shrink-0 items-center gap-2">
                          <Valor centavos={v.saldo_centavos} neutro />
                          <Button
                            variant="ghost"
                            size="icon"
                            aria-label="Desvincular"
                            onClick={() =>
                              v.tipo === "conta"
                                ? vincularConta.mutate({ contaId: v.id, objetivoId: null })
                                : vincularInv.mutate({ investimentoId: v.id, objetivoId: null })
                            }
                          >
                            <X className="size-4" />
                          </Button>
                        </span>
                      </li>
                    ))}
                  </ul>
                )}

                {contasLivres.length + invsLivres.length > 0 ? (
                  <Select onValueChange={adicionar} value="">
                    <SelectTrigger>
                      <SelectValue placeholder="Vincular conta ou investimento…" />
                    </SelectTrigger>
                    <SelectContent>
                      {contasLivres.map((c) => (
                        <SelectItem key={`conta-${c.id}`} value={`conta:${c.id}`}>
                          {c.nome ?? "Conta"}
                        </SelectItem>
                      ))}
                      {invsLivres.map((i) => (
                        <SelectItem key={`inv-${i.id}`} value={`inv:${i.id}`}>
                          {i.nome ?? "Investimento"}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                ) : null}
              </div>
            </div>

            <DialogFooter className="justify-between sm:justify-between">
              <Button
                variant="ghost"
                className="text-destructive"
                disabled={remover.isPending}
                onClick={() =>
                  remover.mutate(id, {
                    onSuccess: () => {
                      toast.success("Objetivo removido.")
                      onClose()
                    },
                    onError: (err) => toast.error(err.message),
                  })
                }
              >
                Remover
              </Button>
              <ObjetivoFormDialog
                objetivo={data}
                trigger={<Button variant="outline">Editar</Button>}
              />
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}
