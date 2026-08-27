import { Plus, Tag, Trash2 } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import { EmptyState } from "@/components/common/empty-state"
import { IconeSelect } from "@/components/configuracoes/icone-select"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Button, buttonVariants } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
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
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import {
  nomeCategoria,
  useAtualizarCategoria,
  useCriarCategoria,
  useRemoverCategoria,
  type Categoria,
  type IconeCategoria,
} from "@/lib/api/categorias"

/** Categorias criadas pelo usuário: criar, renomear, ativar/desativar e excluir (§4.5). */
export function CategoriasPersonalizadasCard({
  categorias,
}: {
  categorias: Categoria[]
}) {
  return (
    <Card>
      <CardHeader className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1.5">
          <CardTitle className="text-base">Minhas categorias</CardTitle>
          <CardDescription>
            Categorias que você criou. Elas não são atribuídas automaticamente —
            use uma regra abaixo, ou escolha na transação.
          </CardDescription>
        </div>
        <NovaCategoriaDialog />
      </CardHeader>
      <CardContent>
        {categorias.length === 0 ? (
          <EmptyState
            icon={Tag}
            title="Nenhuma categoria própria"
            description="Crie uma para classificar gastos que a taxonomia do banco não cobre — “Pet”, “Presentes”, “Faculdade”."
          />
        ) : (
          <ul className="divide-y">
            {categorias.map((c) => (
              <LinhaPersonalizada key={c.pluggy_id} categoria={c} />
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}

function LinhaPersonalizada({ categoria }: { categoria: Categoria }) {
  const atualizar = useAtualizarCategoria()
  const remover = useRemoverCategoria()
  const [nome, setNome] = useState(nomeCategoria(categoria))

  /** Só grava se mudou de verdade — abrir e sair do campo não deve disparar um PATCH. */
  function salvarNome() {
    const limpo = nome.trim()
    if (!limpo || limpo === nomeCategoria(categoria)) {
      setNome(nomeCategoria(categoria))
      return
    }
    atualizar.mutate(
      { id: categoria.pluggy_id, patch: { nome: limpo } },
      {
        onSuccess: () => toast.success("Categoria renomeada."),
        onError: (err) => {
          setNome(nomeCategoria(categoria))
          toast.error(err.message)
        },
      }
    )
  }

  return (
    <li className="flex items-center gap-2 py-2">
      <IconeSelect
        value={categoria.icone}
        nomeCategoria={nomeCategoria(categoria)}
        onChange={(icone) =>
          atualizar.mutate(
            { id: categoria.pluggy_id, patch: { icone } },
            { onError: (err) => toast.error(err.message) }
          )
        }
      />
      <Input
        value={nome}
        onChange={(e) => {
          setNome(e.target.value)
        }}
        onBlur={salvarNome}
        onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
        aria-label={`Nome da categoria ${nomeCategoria(categoria)}`}
        // Borda tênue permanente: `border-transparent` + `:hover` não sinalizava nada em toque,
        // onde não existe hover — o campo parecia texto estático.
        className="h-9 flex-1 border-input/60 bg-transparent px-2 shadow-none"
      />
      <Switch
        checked={categoria.ativa}
        aria-label={`${categoria.ativa ? "Desativar" : "Ativar"} ${nomeCategoria(categoria)}`}
        onCheckedChange={(ativa) =>
          atualizar.mutate(
            { id: categoria.pluggy_id, patch: { ativa } },
            { onError: (err) => toast.error(err.message) }
          )
        }
      />
      <AlertDialog>
        <AlertDialogTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            className="size-9 shrink-0 text-muted-foreground hover:text-destructive"
            aria-label={`Excluir ${nomeCategoria(categoria)}`}
          >
            <Trash2 className="size-4" />
          </Button>
        </AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Excluir “{nomeCategoria(categoria)}”
            </AlertDialogTitle>
            <AlertDialogDescription>
              As transações classificadas nela ficam sem categoria, e as regras
              que apontam para ela são removidas. Se ela estiver em uso em algum
              orçamento, a exclusão é recusada — tire-a de lá antes.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              className={buttonVariants({ variant: "destructive" })}
              onClick={() =>
                remover.mutate(categoria.pluggy_id, {
                  onSuccess: () => toast.success("Categoria excluída."),
                  onError: (err) => toast.error(err.message),
                })
              }
            >
              Excluir
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </li>
  )
}

/** Nome + ícone da categoria nova. Fora do diálogo porque é o único bloco dele com estado
 *  próprio de formulário — o resto é moldura (cabeçalho, rodapé, gatilho). */
function CamposNovaCategoria({
  nome,
  icone,
  onNome,
  onIcone,
}: {
  nome: string
  icone: IconeCategoria
  onNome: (valor: string) => void
  onIcone: (valor: IconeCategoria) => void
}) {
  return (
    <div className="space-y-1.5 py-4">
      <Label htmlFor="nova-categoria">Nome e ícone</Label>
      <div className="flex items-center gap-2">
        <Input
          id="nova-categoria"
          value={nome}
          onChange={(e) => {
            onNome(e.target.value)
          }}
          placeholder="Pet"
          minLength={2}
          maxLength={60}
          autoFocus
          required
        />
        <IconeSelect value={icone} onChange={onIcone} />
      </div>
      <p className="text-xs text-muted-foreground">
        O ícone aparece junto da categoria em transações, orçamentos e
        assinaturas.
      </p>
    </div>
  )
}

function NovaCategoriaDialog() {
  const criar = useCriarCategoria()
  const [aberto, setAberto] = useState(false)
  const [nome, setNome] = useState("")
  // "tag" e não `null`: uma categoria nova já nasce com ícone, e o padrão fica visível no gatilho
  // em vez de esconder a escolha atrás de um estado vazio.
  const [icone, setIcone] = useState<IconeCategoria>("tag")

  function submeter(e: React.FormEvent) {
    e.preventDefault()
    criar.mutate(
      { nome: nome.trim(), icone },
      {
        onSuccess: () => {
          toast.success("Categoria criada.")
          setNome("")
          setIcone("tag")
          setAberto(false)
        },
        onError: (err) => toast.error(err.message),
      }
    )
  }

  return (
    <Dialog open={aberto} onOpenChange={setAberto}>
      <DialogTrigger asChild>
        <Button size="sm" variant="outline">
          <Plus className="size-4" aria-hidden />
          Nova categoria
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={submeter}>
          <DialogHeader>
            <DialogTitle>Nova categoria</DialogTitle>
            <DialogDescription>
              Ela fica disponível em transações, orçamentos, assinaturas e
              divisões, como qualquer outra.
            </DialogDescription>
          </DialogHeader>
          <CamposNovaCategoria
            nome={nome}
            icone={icone}
            onNome={setNome}
            onIcone={setIcone}
          />
          <DialogFooter>
            <DialogClose asChild>
              <Button type="button" variant="outline">
                Cancelar
              </Button>
            </DialogClose>
            <Button type="submit" disabled={nome.trim().length < 2}>
              Criar
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
