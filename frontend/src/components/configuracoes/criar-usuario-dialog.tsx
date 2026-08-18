import { Check, Copy, UserPlus } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

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
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { useCriarUsuarioAdmin, type TipoUsuario } from "@/lib/api/usuarios"

/** "+ Novo usuário" (§4.11): cria um usuário (completo ou só divisão de contas) e devolve um link
 *  de ativação — sem e-mail (decisão #15), o administrador copia e envia o link por fora. */
export function CriarUsuarioDialog() {
  const [aberto, setAberto] = useState(false)
  const [nome, setNome] = useState("")
  const [email, setEmail] = useState("")
  const [tipo, setTipo] = useState<TipoUsuario>("completo")
  const [link, setLink] = useState<string | null>(null)
  const [copiado, setCopiado] = useState(false)
  const criar = useCriarUsuarioAdmin()

  function fechar(v: boolean) {
    setAberto(v)
    if (!v) {
      setNome("")
      setEmail("")
      setTipo("completo")
      setLink(null)
      setCopiado(false)
    }
  }

  function enviar(e: React.FormEvent) {
    e.preventDefault()
    criar.mutate(
      { nome, email, tipo },
      {
        onSuccess: (r) => setLink(`${window.location.origin}${r.link_convite}`),
        onError: (err) => toast.error(err.message),
      }
    )
  }

  async function copiar() {
    if (!link) return
    await navigator.clipboard.writeText(link)
    setCopiado(true)
    toast.success("Link copiado.")
  }

  return (
    <Dialog open={aberto} onOpenChange={fechar}>
      <DialogTrigger asChild>
        <Button>
          <UserPlus className="size-4" /> Novo usuário
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Novo usuário</DialogTitle>
        </DialogHeader>

        {link ? (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Envie este link para {nome} — ao abri-lo, a pessoa define a
              própria senha e passa a ter acesso.
            </p>
            <div className="flex items-center gap-2">
              <Input readOnly value={link} className="font-mono text-xs" />
              <Button
                type="button"
                variant="outline"
                size="icon"
                onClick={copiar}
                aria-label="Copiar link"
              >
                {copiado ? (
                  <Check className="size-4" />
                ) : (
                  <Copy className="size-4" />
                )}
              </Button>
            </div>
            <DialogFooter>
              <DialogClose asChild>
                <Button>Concluir</Button>
              </DialogClose>
            </DialogFooter>
          </div>
        ) : (
          <form className="space-y-4" onSubmit={enviar}>
            <div className="space-y-1.5">
              <Label htmlFor="nome">Nome</Label>
              <Input
                id="nome"
                value={nome}
                onChange={(e) => setNome(e.target.value)}
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="email">E-mail</Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label>Tipo de acesso</Label>
              <RadioGroup
                value={tipo}
                onValueChange={(v) => setTipo(v as TipoUsuario)}
              >
                <Label className="flex items-start gap-2 rounded-md border p-3 text-sm font-normal has-data-checked:border-primary has-data-checked:bg-primary/5">
                  <RadioGroupItem value="completo" className="mt-0.5" />
                  <span>
                    <span className="block font-medium">Completo</span>
                    <span className="block text-muted-foreground">
                      Acesso a todo o app.
                    </span>
                  </span>
                </Label>
                <Label className="flex items-start gap-2 rounded-md border p-3 text-sm font-normal has-data-checked:border-primary has-data-checked:bg-primary/5">
                  <RadioGroupItem value="divisao" className="mt-0.5" />
                  <span>
                    <span className="block font-medium">Divisão de contas</span>
                    <span className="block text-muted-foreground">
                      Só enxerga o módulo de divisão de contas.
                    </span>
                  </span>
                </Label>
              </RadioGroup>
            </div>
            <DialogFooter>
              <DialogClose asChild>
                <Button type="button" variant="ghost">
                  Cancelar
                </Button>
              </DialogClose>
              <Button
                type="submit"
                disabled={!nome || !email || criar.isPending}
              >
                Gerar convite
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  )
}
