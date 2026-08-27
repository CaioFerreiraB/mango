import { Pencil, Plus, Trash2, Wand2 } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import { EmptyState } from "@/components/common/empty-state"
import { CategoriaSelect } from "@/components/transacoes/categoria-select"
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
import { Badge } from "@/components/ui/badge"
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
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { useMapaCategorias } from "@/lib/api/categorias"
import {
  MAX_REGRAS,
  ROTULO_TIPO_MATCH,
  useAtualizarRegra,
  useCriarRegra,
  useRegrasCategorizacao,
  useRemoverRegra,
  type RegraCategorizacao,
  type TipoMatch,
} from "@/lib/api/regras-categorizacao"

const TEXTO_MIN = 3

/** Os quatro estados da lista (erro, carregando, vazia, preenchida). Separado do card porque é a
 *  única parte dele que depende da query — o resto é cabeçalho e gatilho, que não mudam. */
function ConteudoRegras({
  regras,
  categorias,
}: {
  regras: ReturnType<typeof useRegrasCategorizacao>
  categorias: Map<string, string>
}) {
  if (regras.isError)
    return <EmptyState title="Não foi possível carregar as regras" />
  if (regras.isLoading) return <Skeleton className="h-40 w-full" />
  if (regras.data?.length === 0)
    return (
      <EmptyState
        icon={Wand2}
        title="Nenhuma regra ainda"
        description="Exemplo: “contém uber” → Transporte. Toda transação com esse texto no nome passa a cair nessa categoria."
      />
    )

  return (
    <>
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Texto</TableHead>
              <TableHead>Como casa</TableHead>
              <TableHead>Categoria</TableHead>
              <TableHead className="w-20 text-right">Ações</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {regras.data?.map((r) => (
              <LinhaRegra
                key={r.id}
                regra={r}
                categoria={categorias.get(r.categoria_id)}
              />
            ))}
          </TableBody>
        </Table>
      </div>
      <p className="text-xs text-muted-foreground">
        {regras.data?.length} de {MAX_REGRAS} regras.
      </p>
    </>
  )
}

/** Mapeamento automático nome da transação → categoria (§4.5). */
export function RegrasCategorizacaoCard() {
  const regras = useRegrasCategorizacao()
  const categorias = useMapaCategorias()

  return (
    <Card>
      <CardHeader className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1.5">
          <CardTitle className="text-base">Regras automáticas</CardTitle>
          <CardDescription>
            Ensine uma vez e vale para o histórico e para o que chegar depois. A
            regra perde para um ajuste que você tenha feito numa transação
            específica, e para a categoria de uma assinatura.
          </CardDescription>
        </div>
        <RegraDialog
          gatilho={
            <Button
              size="sm"
              variant="outline"
              disabled={(regras.data?.length ?? 0) >= MAX_REGRAS}
            >
              <Plus className="size-4" aria-hidden />
              Nova regra
            </Button>
          }
        />
      </CardHeader>
      <CardContent className="space-y-3">
        <ConteudoRegras regras={regras} categorias={categorias} />
      </CardContent>
    </Card>
  )
}

function LinhaRegra({
  regra,
  categoria,
}: {
  regra: RegraCategorizacao
  categoria: string | undefined
}) {
  const remover = useRemoverRegra()

  return (
    <TableRow>
      <TableCell className="font-medium">{regra.texto}</TableCell>
      <TableCell>
        <Badge variant="secondary">{ROTULO_TIPO_MATCH[regra.tipo_match]}</Badge>
      </TableCell>
      <TableCell className="text-muted-foreground">
        {categoria ?? "—"}
      </TableCell>
      <TableCell className="text-right">
        <div className="flex justify-end gap-1">
          <RegraDialog
            regra={regra}
            gatilho={
              <Button
                variant="ghost"
                size="icon"
                className="size-8"
                aria-label={`Editar regra ${regra.texto}`}
              >
                <Pencil className="size-4" />
              </Button>
            }
          />
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="size-8 text-muted-foreground hover:text-destructive"
                aria-label={`Excluir regra ${regra.texto}`}
              >
                <Trash2 className="size-4" />
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Excluir regra</AlertDialogTitle>
                <AlertDialogDescription>
                  As transações que caíram nesta categoria por causa dela voltam
                  à classificação do banco. Ajustes feitos à mão não mudam.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancelar</AlertDialogCancel>
                <AlertDialogAction
                  className={buttonVariants({ variant: "destructive" })}
                  onClick={() =>
                    remover.mutate(regra.id, {
                      onSuccess: () => toast.success("Regra excluída."),
                      onError: (err) => toast.error(err.message),
                    })
                  }
                >
                  Excluir
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </TableCell>
    </TableRow>
  )
}

/** Criar ou editar — o mesmo formulário; `regra` presente significa edição. */
/** "Contém" vs. "exato", com a explicação de cada um. Bloco próprio porque o texto explicativo é
 *  o que decide a escolha e ocupa mais espaço que todo o resto do formulário junto. */
function EscolhaTipoMatch({
  valor,
  onMudar,
}: {
  valor: TipoMatch
  onMudar: (novo: TipoMatch) => void
}) {
  return (
    <div className="space-y-2">
      <Label>Como casar</Label>
      <RadioGroup
        value={valor}
        onValueChange={(v) => {
          onMudar(v as TipoMatch)
        }}
      >
        <label className="flex items-start gap-2 text-sm">
          <RadioGroupItem value="contem" className="mt-0.5" />
          <span className="flex flex-col gap-0.5">
            <span className="font-medium">Contém o texto</span>
            <span className="text-muted-foreground">
              Casa “UBER *TRIP 4521”. É o que você quer na maioria dos casos — o
              banco costuma anexar códigos ao nome.
            </span>
          </span>
        </label>
        <label className="flex items-start gap-2 text-sm">
          <RadioGroupItem value="exato" className="mt-0.5" />
          <span className="flex flex-col gap-0.5">
            <span className="font-medium">Texto exato</span>
            <span className="text-muted-foreground">
              Casa só o nome inteiro, idêntico. Tem precedência sobre as regras
              de “contém”.
            </span>
          </span>
        </label>
      </RadioGroup>
    </div>
  )
}

export function RegraDialog({
  regra,
  gatilho,
  textoInicial,
  categoriaInicial,
}: {
  regra?: RegraCategorizacao
  gatilho: React.ReactNode
  textoInicial?: string
  categoriaInicial?: string | null
}) {
  const criar = useCriarRegra()
  const atualizar = useAtualizarRegra()
  const [aberto, setAberto] = useState(false)
  const [texto, setTexto] = useState(regra?.texto ?? textoInicial ?? "")
  const [tipo, setTipo] = useState<TipoMatch>(regra?.tipo_match ?? "contem")
  const [categoriaId, setCategoriaId] = useState<string | null>(
    regra?.categoria_id ?? categoriaInicial ?? null
  )

  const valido = texto.trim().length >= TEXTO_MIN && categoriaId !== null

  /** Recarrega o formulário a cada abertura: o `useState` só lê os props na PRIMEIRA montagem,
   *  então sem isto reabrir mostraria o valor antigo (ou um rascunho abandonado). */
  function alternar(proximo: boolean) {
    if (proximo) {
      setTexto(regra?.texto ?? textoInicial ?? "")
      setTipo(regra?.tipo_match ?? "contem")
      setCategoriaId(regra?.categoria_id ?? categoriaInicial ?? null)
    }
    setAberto(proximo)
  }

  function submeter(e: React.FormEvent) {
    e.preventDefault()
    if (!valido || categoriaId === null) return
    const corpo = {
      texto: texto.trim(),
      tipo_match: tipo,
      categoria_id: categoriaId,
    }
    const opcoes = {
      onSuccess: () => {
        toast.success(regra ? "Regra atualizada." : "Regra criada.")
        setAberto(false)
      },
      onError: (err: Error) => toast.error(err.message),
    }
    if (regra) atualizar.mutate({ id: regra.id, patch: corpo }, opcoes)
    else criar.mutate(corpo, opcoes)
  }

  return (
    <Dialog open={aberto} onOpenChange={alternar}>
      <DialogTrigger asChild>{gatilho}</DialogTrigger>
      <DialogContent>
        <form onSubmit={submeter}>
          <DialogHeader>
            <DialogTitle>{regra ? "Editar regra" : "Nova regra"}</DialogTitle>
            <DialogDescription>
              O texto é comparado com o nome do estabelecimento e com a
              descrição do banco, ignorando maiúsculas e acentos.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-1.5">
              <Label htmlFor="regra-texto">Texto</Label>
              <Input
                id="regra-texto"
                value={texto}
                onChange={(e) => {
                  setTexto(e.target.value)
                }}
                placeholder="uber"
                minLength={TEXTO_MIN}
                maxLength={120}
                autoFocus
                required
              />
              <p className="text-xs text-muted-foreground">
                No mínimo {TEXTO_MIN} caracteres — um texto muito curto casaria
                quase tudo.
              </p>
            </div>
            <EscolhaTipoMatch valor={tipo} onMudar={setTipo} />
            <div className="space-y-1.5">
              <Label>Categoria</Label>
              <CategoriaSelect value={categoriaId} onChange={setCategoriaId} />
            </div>
          </div>
          <DialogFooter>
            <DialogClose asChild>
              <Button type="button" variant="outline">
                Cancelar
              </Button>
            </DialogClose>
            <Button type="submit" disabled={!valido}>
              {regra ? "Salvar" : "Criar regra"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
