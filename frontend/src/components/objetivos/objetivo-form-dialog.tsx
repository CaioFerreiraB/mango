import { useState } from "react"
import { toast } from "sonner"

import { CurrencyInput } from "@/components/common/currency-input"
import { Button } from "@/components/ui/button"
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
import { Textarea } from "@/components/ui/textarea"
import { useAtualizarObjetivo, useCriarObjetivo, type Objetivo } from "@/lib/api/objetivos"

/** Modal de criar/editar objetivo — mesmo formulário serve os dois casos (`objetivo` opcional). */
export function ObjetivoFormDialog({
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
    alvoCentavos: objetivo?.valor_alvo_centavos ?? 0,
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
      valor_alvo_centavos: form.alvoCentavos,
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
            <Label htmlFor="alvo">Valor-alvo</Label>
            <CurrencyInput
              id="alvo"
              value={form.alvoCentavos}
              onChange={(c) => setForm({ ...form, alvoCentavos: c })}
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
            <Button type="submit" disabled={!form.titulo || form.alvoCentavos <= 0 || pendente}>
              Salvar
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
