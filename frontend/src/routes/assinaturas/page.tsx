import {
  Ban,
  ChevronRight,
  Loader2,
  Pencil,
  PieChart,
  Plus,
  Repeat,
  Search,
  Sparkles,
  Trash2,
  TrendingDown,
  TrendingUp,
  Users,
  X,
} from "lucide-react"
import type { LucideIcon } from "lucide-react"
import { createElement, useId, useState } from "react"
import { toast } from "sonner"

import { CategoriaSelect } from "@/components/transacoes/categoria-select"
import { EmptyState } from "@/components/common/empty-state"
import { iconeCategoria } from "@/lib/api/categoria-icones"
import { useMe } from "@/lib/api/auth"
import { ilustracao } from "@/lib/illustrations"
import { Valor } from "@/components/common/valor"
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
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"
import { useMapaCategorias } from "@/lib/api/categorias"
import {
  useAssinaturas,
  useAtualizarAssinatura,
  useCandidatosAssinatura,
  useCriarAssinatura,
  useCriarAssinaturasEmLote,
  useRemoverAssinatura,
  useResumoAssinaturas,
  type Assinatura,
  type AssinaturaCreate,
  type AssinaturaResumo,
  type Periodicidade,
} from "@/lib/api/assinaturas"
import { useMarcarNaoAssinatura } from "@/lib/api/transacoes"
import { formatBRL, formatMoeda } from "@/lib/format"
import { cn } from "@/lib/utils"

const PERIODICIDADES: Periodicidade[] = [
  "mensal",
  "trimestral",
  "semestral",
  "anual",
  "irregular",
]

function centavos(reais: string): number {
  return Math.round(Number(reais) * 100)
}

export function AssinaturasPage() {
  const assinaturas = useAssinaturas()
  const resumo = useResumoAssinaturas()
  const nomes = useMapaCategorias()
  // undefined = sem filtro; null = "Sem categoria"; string = categoria específica.
  const [categoriaFiltro, setCategoriaFiltro] = useState<
    string | null | undefined
  >(undefined)

  const lista = [...(assinaturas.data ?? [])].sort(
    (a, b) => Number(b.ativa) - Number(a.ativa) || a.nome.localeCompare(b.nome)
  )
  const valoresAtivas = lista
    .filter((a) => a.ativa)
    .map((a) => a.valor_centavos)
  const listaFiltrada =
    categoriaFiltro === undefined
      ? lista
      : lista.filter((a) => (a.categoria_id ?? null) === categoriaFiltro)
  const rotuloFiltro =
    categoriaFiltro == null
      ? "Sem categoria"
      : (nomes.get(categoriaFiltro) ?? categoriaFiltro)

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Assinaturas</h1>
          <p className="text-sm text-muted-foreground">
            Gastos recorrentes. As detectadas no sync vêm marcadas para você
            confirmar.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <BuscarAssinaturasDialog />
          <AssinaturaFormDialog
            trigger={
              <Button>
                <Plus className="size-4" /> Nova assinatura
              </Button>
            }
          />
        </div>
      </header>

      {resumo.data ? (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <CardTotalMensal
            total={resumo.data.total_mensal_centavos}
            qtdAtivas={valoresAtivas.length}
            maior={valoresAtivas.length ? Math.max(...valoresAtivas) : 0}
            menor={valoresAtivas.length ? Math.min(...valoresAtivas) : 0}
          />
          <Card>
            <CardHeader className="pb-0">
              <CardTitle className="text-base">Por categoria</CardTitle>
            </CardHeader>
            <CardContent>
              <GraficoPorCategoria
                itens={resumo.data.por_categoria}
                nomes={nomes}
                selecionada={categoriaFiltro}
                onSelecionar={setCategoriaFiltro}
              />
            </CardContent>
          </Card>
        </div>
      ) : null}

      {assinaturas.isError ? (
        <EmptyState title="Não foi possível carregar as assinaturas" />
      ) : assinaturas.isLoading ? (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      ) : lista.length === 0 ? (
        <EmptyState
          icon={Repeat}
          title="Nenhuma assinatura"
          description="Adicione as assinaturas vigentes ou rode um sync para detectá-las automaticamente."
        >
          <AssinaturaFormDialog
            trigger={
              <Button>
                <Plus className="size-4" /> Nova assinatura
              </Button>
            }
          />
        </EmptyState>
      ) : (
        <div className="space-y-2">
          {categoriaFiltro !== undefined ? (
            <div className="flex items-center gap-2">
              <Badge variant="secondary" className="gap-1 pr-1">
                {rotuloFiltro}
                <button
                  type="button"
                  className="rounded-sm opacity-70 hover:opacity-100"
                  onClick={() => setCategoriaFiltro(undefined)}
                  aria-label="Limpar filtro de categoria"
                >
                  <X className="size-3" />
                </button>
              </Badge>
              <span className="text-xs text-muted-foreground">
                {listaFiltrada.length} de {lista.length}
              </span>
            </div>
          ) : null}
          {listaFiltrada.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">
              Nenhuma assinatura nessa categoria.
            </p>
          ) : (
            listaFiltrada.map((a) => (
              <AssinaturaRow
                key={a.id}
                assinatura={a}
                categoriaNome={
                  a.categoria_id ? nomes.get(a.categoria_id) : undefined
                }
              />
            ))
          )}
        </div>
      )}
    </div>
  )
}

function AssinaturaRow({
  assinatura,
  categoriaNome,
}: {
  assinatura: Assinatura
  categoriaNome?: string
}) {
  const [aberto, setAberto] = useState(false)

  return (
    <>
      <Card
        className={cn(
          "gap-0 overflow-hidden p-0",
          !assinatura.ativa && "opacity-60"
        )}
      >
        <button
          type="button"
          onClick={() => setAberto(true)}
          className="flex w-full items-center gap-3 px-4 py-4 text-left transition-colors hover:bg-muted/50"
        >
          <span
            aria-hidden
            className="grid size-11 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary"
          >
            {createElement(iconeCategoria(assinatura.categoria_id), {
              className: "size-5",
            })}
          </span>
          <div className="min-w-0 flex-1">
            <p className="flex items-center gap-2 font-medium">
              <span className="truncate">{assinatura.nome}</span>
              {assinatura.detectada_automaticamente ? (
                <Badge
                  variant="secondary"
                  className="gap-1 bg-primary/10 text-primary hover:bg-primary/10"
                >
                  <Repeat className="size-3" /> auto
                </Badge>
              ) : null}
              {!assinatura.ativa ? (
                <Badge variant="secondary">Inativa</Badge>
              ) : null}
            </p>
            <p className="text-xs text-muted-foreground">
              <Valor centavos={assinatura.valor_centavos} neutro /> ·{" "}
              {assinatura.periodicidade}
              {categoriaNome ? ` · ${categoriaNome}` : ""}
            </p>
          </div>
          <ChevronRight className="size-4 shrink-0 text-muted-foreground" />
        </button>
      </Card>
      <AssinaturaFormDialog
        assinatura={assinatura}
        open={aberto}
        onOpenChange={setAberto}
      />
    </>
  )
}

function AssinaturaFormDialog({
  trigger,
  assinatura,
  open,
  onOpenChange,
}: {
  trigger?: React.ReactNode
  assinatura?: Assinatura
  open?: boolean
  onOpenChange?: (v: boolean) => void
}) {
  // Controlado quando `open`/`onOpenChange` vêm de fora (card clicável); senão, estado interno + trigger.
  const [interno, setInterno] = useState(false)
  const aberto = open ?? interno
  const setAberto = onOpenChange ?? setInterno
  const formId = useId()
  const [form, setForm] = useState({
    nome: assinatura?.nome ?? "",
    valor: assinatura ? String(assinatura.valor_centavos / 100) : "",
    periodicidade: (assinatura?.periodicidade ?? "mensal") as Periodicidade,
    categoria_id: assinatura?.categoria_id ?? null,
    data_inicio: assinatura?.data_inicio ?? "",
    nomes_transacao: assinatura?.nomes_transacao ?? [],
    ativa: assinatura?.ativa ?? true,
  })
  const criar = useCriarAssinatura()
  const atualizar = useAtualizarAssinatura()
  const remover = useRemoverAssinatura()
  const pendente = criar.isPending || atualizar.isPending

  function salvar(e: React.FormEvent) {
    e.preventDefault()
    const body = {
      nome: form.nome,
      valor_centavos: centavos(form.valor),
      periodicidade: form.periodicidade,
      categoria_id: form.categoria_id,
      data_inicio: form.data_inicio || null,
      nomes_transacao: form.nomes_transacao,
    }
    const onSuccess = () => {
      toast.success(
        assinatura ? "Assinatura atualizada." : "Assinatura criada."
      )
      setAberto(false)
    }
    const onError = (err: Error) => toast.error(err.message)
    if (assinatura)
      atualizar.mutate(
        { id: assinatura.id, patch: { ...body, ativa: form.ativa } },
        { onSuccess, onError }
      )
    else
      criar.mutate(
        { ...body, ativa: true, detectada_automaticamente: false },
        { onSuccess, onError }
      )
  }

  return (
    <Dialog open={aberto} onOpenChange={setAberto}>
      {trigger ? <DialogTrigger asChild>{trigger}</DialogTrigger> : null}
      <DialogContent className="flex max-h-[calc(100dvh-2rem)] flex-col gap-0 overflow-hidden p-0 sm:max-w-xl">
        <DialogHeader className="shrink-0 flex-row items-start gap-3 space-y-0 p-4 pr-10">
          <span
            aria-hidden
            className="grid size-11 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary"
          >
            {assinatura ? (
              <Pencil className="size-5" />
            ) : (
              <Plus className="size-5" />
            )}
          </span>
          <div className="space-y-1.5">
            <DialogTitle>
              {assinatura ? "Editar assinatura" : "Nova assinatura"}
            </DialogTitle>
            <DialogDescription>
              {assinatura
                ? "Ajuste os detalhes desta assinatura."
                : "Cadastre um gasto recorrente para acompanhar."}
            </DialogDescription>
          </div>
        </DialogHeader>
        <form
          id={formId}
          className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4"
          onSubmit={salvar}
        >
          <div className="space-y-1.5">
            <Label htmlFor="nome">Nome</Label>
            <Input
              id="nome"
              value={form.nome}
              onChange={(e) => setForm({ ...form, nome: e.target.value })}
              required
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="valor">Valor (R$)</Label>
              <Input
                id="valor"
                type="number"
                min="0"
                step="0.01"
                value={form.valor}
                onChange={(e) => setForm({ ...form, valor: e.target.value })}
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label>Periodicidade</Label>
              <Select
                value={form.periodicidade}
                onValueChange={(v) =>
                  setForm({ ...form, periodicidade: v as Periodicidade })
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {PERIODICIDADES.map((p) => (
                    <SelectItem key={p} value={p} className="capitalize">
                      {p}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="space-y-1.5">
            <Label>Categoria</Label>
            <CategoriaSelect
              value={form.categoria_id}
              onChange={(v) => setForm({ ...form, categoria_id: v })}
              placeholder="Sem categoria"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="inicio">Início (opcional)</Label>
            <Input
              id="inicio"
              type="date"
              value={form.data_inicio}
              onChange={(e) =>
                setForm({ ...form, data_inicio: e.target.value })
              }
            />
          </div>
          <NomesTransacaoInput
            valores={form.nomes_transacao}
            onChange={(nomes_transacao) =>
              setForm({ ...form, nomes_transacao })
            }
          />
          {assinatura ? (
            <label className="flex items-center justify-between gap-3 rounded-lg border p-3">
              <span>
                <span className="block text-sm font-medium">
                  Assinatura ativa
                </span>
                <span className="block text-xs text-muted-foreground">
                  Contabiliza no total mensal e nos alertas.
                </span>
              </span>
              <Switch
                checked={form.ativa}
                onCheckedChange={(v) => setForm({ ...form, ativa: v })}
              />
            </label>
          ) : null}
        </form>
        <DialogFooter className="mx-0 mb-0 shrink-0 sm:items-center sm:justify-between">
          {assinatura ? (
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button
                  type="button"
                  variant="ghost"
                  className="text-destructive hover:text-destructive"
                  disabled={remover.isPending}
                >
                  <Trash2 className="size-4" /> Excluir
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Excluir assinatura?</AlertDialogTitle>
                  <AlertDialogDescription>
                    A assinatura «{assinatura.nome}» será removida. As
                    transações vinculadas são desvinculadas, mas não apagadas.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancelar</AlertDialogCancel>
                  <AlertDialogAction
                    className={buttonVariants({ variant: "destructive" })}
                    onClick={() =>
                      remover.mutate(assinatura.id, {
                        onSuccess: () => {
                          toast.success("Assinatura removida.")
                          setAberto(false)
                        },
                        onError: (err) => toast.error(err.message),
                      })
                    }
                  >
                    Excluir
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          ) : (
            <span className="hidden sm:block" />
          )}
          <div className="flex flex-col-reverse gap-2 sm:flex-row">
            <DialogClose asChild>
              <Button type="button" variant="outline">
                Cancelar
              </Button>
            </DialogClose>
            <Button
              type="submit"
              form={formId}
              disabled={!form.nome || !form.valor || pendente}
            >
              Salvar
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/** Editor de aliases (chips): digita + Enter/vírgula adiciona (dedup case-insensitive), ✕ remove.
 *  Os nomes casam transações com a assinatura no sync e evitam re-sugestão na busca (§4.7). */
function NomesTransacaoInput({
  valores,
  onChange,
}: {
  valores: string[]
  onChange: (v: string[]) => void
}) {
  const [texto, setTexto] = useState("")

  function adicionar() {
    const nome = texto.trim()
    if (nome && !valores.some((v) => v.toLowerCase() === nome.toLowerCase())) {
      onChange([...valores, nome])
    }
    setTexto("")
  }

  return (
    <div className="space-y-1.5">
      <Label htmlFor="nomes-transacao">Nomes de transação</Label>
      {valores.length ? (
        <div className="flex flex-wrap gap-1.5">
          {valores.map((v) => (
            <Badge key={v} variant="secondary" className="gap-1 pr-1">
              <span className="break-all">{v}</span>
              <button
                type="button"
                className="rounded-sm opacity-70 hover:opacity-100"
                onClick={() => onChange(valores.filter((x) => x !== v))}
                aria-label={`Remover ${v}`}
              >
                <X className="size-3" />
              </button>
            </Badge>
          ))}
        </div>
      ) : null}
      <Input
        id="nomes-transacao"
        value={texto}
        onChange={(e) => setTexto(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === ",") {
            e.preventDefault()
            adicionar()
          }
        }}
        onBlur={adicionar}
        placeholder="Digite e Enter para adicionar"
      />
      <p className="text-xs text-muted-foreground">
        Descrições de transação usadas para casar cobranças automaticamente no
        sync.
      </p>
    </div>
  )
}

/** Card do total mensal estimado: número + mascote grande sangrando no topo e, por baixo, os chips
 *  de fato (ativas / maior / menor) sobre painel tintado do accent (DESIGN.md §Illustrations). */
function CardTotalMensal({
  total,
  qtdAtivas,
  maior,
  menor,
}: {
  total: number
  qtdAtivas: number
  maior: number
  menor: number
}) {
  const me = useMe()
  return (
    <Card className="relative gap-0 overflow-hidden py-0">
      {/* decorativos → ilustração → dados (empilhamento de trás p/ frente) */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-gradient-to-br from-primary/15 via-primary/5 to-transparent"
      />
      <CardContent className="relative flex flex-col gap-4 p-4 sm:p-5">
        {/* valor no topo */}
        <div className="relative z-10">
          <p className="text-sm font-medium text-muted-foreground">
            Total mensal (estimado)
          </p>
          <Valor
            centavos={total}
            neutro
            className="text-4xl font-bold md:text-5xl"
          />
        </div>
        {/* mascote centralizado abaixo do valor */}
        <div className="flex h-72 items-end justify-center">
          <img
            src={ilustracao(me.data?.avatar, "subscriptions")}
            alt=""
            className="pointer-events-none h-full max-w-full object-contain"
          />
        </div>
        {/* chips na parte de baixo, largura total */}
        <div className="grid grid-cols-3 gap-2 sm:gap-2.5">
          <StatChip
            icon={Users}
            valor={
              <span className="text-sm font-bold tabular-nums sm:text-lg">
                {qtdAtivas}
              </span>
            }
            rotulo="assinaturas ativas"
          />
          <StatChip
            icon={TrendingUp}
            valor={
              <Valor
                centavos={maior}
                neutro
                className="text-sm font-bold sm:text-lg"
              />
            }
            rotulo="maior valor"
          />
          <StatChip
            icon={TrendingDown}
            valor={
              <Valor
                centavos={menor}
                neutro
                className="text-sm font-bold sm:text-lg"
              />
            }
            rotulo="menor valor"
          />
        </div>
      </CardContent>
    </Card>
  )
}

/** Chip de fato: ícone tintado do accent, valor destacado e rótulo — sobre painel translúcido
 *  para ficar legível por cima do gradiente/ilustração (dados sempre por cima). */
function StatChip({
  icon: Icon,
  valor,
  rotulo,
}: {
  icon: LucideIcon
  valor: React.ReactNode
  rotulo: string
}) {
  return (
    <div className="rounded-xl border border-border/60 bg-background/70 p-2.5 backdrop-blur-sm sm:p-3">
      <span
        aria-hidden
        className="grid size-8 place-items-center rounded-lg bg-primary/10 text-primary"
      >
        <Icon className="size-4" />
      </span>
      <div className="mt-2 leading-tight">{valor}</div>
      <p className="text-xs text-muted-foreground">{rotulo}</p>
    </div>
  )
}

/** Total mensal por categoria: ícone da categoria (chip do accent), nome + barra proporcional e
 *  valor + `(%)`. Cada linha é clicável e filtra a lista; rodapé conta as categorias. */
function GraficoPorCategoria({
  itens,
  nomes,
  selecionada,
  onSelecionar,
}: {
  itens: AssinaturaResumo["por_categoria"]
  nomes: Map<string, string>
  selecionada: string | null | undefined
  onSelecionar: (categoria: string | null | undefined) => void
}) {
  const dados = itens
    .filter((c) => c.total_mensal_centavos > 0)
    .map((c) => ({
      id: c.categoria_id ?? null,
      label: c.categoria_id
        ? (nomes.get(c.categoria_id) ?? c.categoria_id)
        : "Sem categoria",
      valor: c.total_mensal_centavos,
    }))
    .sort((a, b) => b.valor - a.valor)
  if (dados.length === 0)
    return (
      <p className="text-sm text-muted-foreground">Sem assinaturas vigentes.</p>
    )

  const total = dados.reduce((s, d) => s + d.valor, 0)
  const maximo = Math.max(...dados.map((d) => d.valor))

  return (
    <div>
      <div className="space-y-1">
        {dados.map((d) => {
          const pct = total > 0 ? Math.round((d.valor / total) * 100) : 0
          const largura = maximo > 0 ? (d.valor / maximo) * 100 : 0
          const ativo = selecionada !== undefined && d.id === selecionada
          const Icone = iconeCategoria(d.id)
          return (
            <button
              key={d.id ?? "sem-categoria"}
              type="button"
              aria-pressed={ativo}
              onClick={() => onSelecionar(ativo ? undefined : d.id)}
              className={cn(
                "grid w-full grid-cols-[auto_1fr_auto] items-center gap-3 rounded-lg px-2 py-2 text-left transition-colors hover:bg-muted/60",
                ativo && "bg-muted"
              )}
            >
              <span
                aria-hidden
                className="grid size-9 place-items-center rounded-lg bg-primary/10 text-primary"
              >
                <Icone className="size-4.5" />
              </span>
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">{d.label}</p>
                <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-primary/10">
                  <div
                    className="h-full rounded-full bg-primary"
                    style={{ width: `${largura}%` }}
                  />
                </div>
              </div>
              <span className="text-sm whitespace-nowrap tabular-nums">
                {formatBRL(d.valor)}{" "}
                <span className="text-muted-foreground">({pct}%)</span>
              </span>
            </button>
          )
        })}
      </div>
      <div className="mt-4 flex items-center gap-3 border-t pt-4">
        <span
          aria-hidden
          className="grid size-9 place-items-center rounded-lg bg-primary/10 text-primary"
        >
          <PieChart className="size-4.5" />
        </span>
        <div>
          <p className="text-sm font-medium">
            {dados.length} categoria{dados.length === 1 ? "" : "s"}
          </p>
          <p className="text-xs text-muted-foreground">
            Distribuição das suas assinaturas
          </p>
        </div>
      </div>
    </div>
  )
}

/** Rótulo + valor de um fato do candidato (rótulo pequeno em cima, valor embaixo).
 *  Fica numa grade responsiva no card: colunas se reorganizam quando não cabem. */
function Fato({
  rotulo,
  children,
}: {
  rotulo: string
  children: React.ReactNode
}) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-muted-foreground">{rotulo}</dt>
      <dd className="truncate font-medium tabular-nums">{children}</dd>
    </div>
  )
}

/** Busca sob demanda de assinaturas: loading → lista com switches (default off) → adiciona as escolhidas. */
function BuscarAssinaturasDialog() {
  const [aberto, setAberto] = useState(false)
  // Chaveado por nome (não índice): sobrevive ao refetch quando um candidato é dispensado.
  const [selecionadas, setSelecionadas] = useState<Record<string, boolean>>({})
  const nomes = useMapaCategorias()
  const candidatos = useCandidatosAssinatura(aberto)
  const criarLote = useCriarAssinaturasEmLote()
  const marcarNaoAssinatura = useMarcarNaoAssinatura()

  function abrir(v: boolean) {
    setAberto(v)
    if (!v) setSelecionadas({}) // reset ao fechar; a próxima abertura busca do zero
  }

  const lista = candidatos.data ?? []
  const escolhidas = lista.filter((c) => selecionadas[c.nome])
  const alternar = (nome: string) =>
    setSelecionadas((s) => ({ ...s, [nome]: !s[nome] }))

  function adicionar() {
    const bodies: AssinaturaCreate[] = escolhidas.map((c) => ({
      nome: c.nome,
      valor_centavos: c.valor_centavos,
      periodicidade: c.periodicidade,
      categoria_id: c.categoria_id,
      conta_id: c.conta_id,
      data_inicio: c.data_inicio,
      ativa: true,
      detectada_automaticamente: true,
      // Semeia o alias com o nome da transação → o sync casa cobranças futuras iguais.
      nomes_transacao: [c.nome],
    }))
    criarLote.mutate(bodies, {
      onSuccess: ({ criadas, falhas }) => {
        toast.success(
          `${criadas} assinatura${criadas === 1 ? "" : "s"} adicionada${criadas === 1 ? "" : "s"}.` +
            (falhas ? ` ${falhas} não pôde ser adicionada.` : "")
        )
        abrir(false)
      },
      onError: (err) => toast.error(err.message),
    })
  }

  return (
    <Dialog open={aberto} onOpenChange={abrir}>
      <DialogTrigger asChild>
        <Button variant="outline">
          <Sparkles className="size-4" /> Buscar assinaturas
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader className="flex-row items-start gap-3 space-y-0 pr-6">
          <span
            aria-hidden
            className="grid size-11 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary"
          >
            <Search className="size-5" />
          </span>
          <div className="space-y-1.5">
            <DialogTitle>Buscar assinaturas</DialogTitle>
            <DialogDescription>
              Cobranças recorrentes detectadas nas suas transações. Escolha
              quais adicionar, ou marque "Não é assinatura" para não sugerir de
              novo.
            </DialogDescription>
          </div>
        </DialogHeader>

        {candidatos.isLoading ? (
          <div
            role="status"
            className="flex items-center justify-center gap-2 py-10 text-sm text-muted-foreground"
          >
            <Loader2 className="size-5 animate-spin" />
            Buscando assinaturas…
          </div>
        ) : candidatos.isError ? (
          <p className="py-10 text-center text-sm text-muted-foreground">
            Não foi possível buscar assinaturas.
          </p>
        ) : lista.length === 0 ? (
          <p className="py-10 text-center text-sm text-muted-foreground">
            Nenhuma assinatura nova encontrada nas suas transações.
          </p>
        ) : (
          <ul className="max-h-[60vh] space-y-3 overflow-y-auto">
            {lista.map((c) => {
              const cat = c.categoria_id ? nomes.get(c.categoria_id) : undefined
              const Icone = iconeCategoria(c.categoria_id)
              const selecionada = selecionadas[c.nome] ?? false
              return (
                <li key={c.nome}>
                  {/* Card inteiro seleciona/desseleciona; o toggle "Não é assinatura" para de propagar. */}
                  <div
                    role="button"
                    tabIndex={0}
                    aria-pressed={selecionada}
                    onClick={() => alternar(c.nome)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault()
                        alternar(c.nome)
                      }
                    }}
                    className={cn(
                      "cursor-pointer rounded-xl border p-4 transition-colors outline-none focus-visible:ring-2 focus-visible:ring-ring",
                      selecionada
                        ? "border-primary bg-primary/5"
                        : "hover:border-primary/40 hover:bg-muted/40"
                    )}
                  >
                    <div className="flex items-start gap-3">
                      <span
                        aria-hidden
                        className="grid size-11 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary"
                      >
                        <Icone className="size-5" />
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="font-medium break-words">{c.nome}</p>
                        <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
                          <Fato rotulo="Valor">
                            {formatBRL(c.valor_centavos)}
                          </Fato>
                          {c.moeda !== "BRL" &&
                          c.valor_moeda_centavos != null ? (
                            <Fato rotulo="Moeda estrangeira">
                              {formatMoeda(c.valor_moeda_centavos, c.moeda)}
                            </Fato>
                          ) : null}
                          <Fato rotulo="Cobranças">{c.ocorrencias}</Fato>
                          <Fato rotulo="Periodicidade">
                            <span className="capitalize">
                              {c.periodicidade}
                            </span>
                          </Fato>
                        </dl>
                      </div>
                    </div>
                    <div className="mt-4 flex flex-col gap-3 border-t border-dashed pt-4 sm:flex-row sm:items-center sm:justify-between">
                      <div className="min-w-0">
                        <p className="text-xs text-muted-foreground">
                          Categoria
                        </p>
                        <p className="mt-0.5 flex items-center gap-1.5 text-sm font-medium">
                          <Icone className="size-4 shrink-0 text-primary" />
                          {cat ?? "Sem categoria"}
                        </p>
                      </div>
                      {/* Ação separada da seleção: stopPropagation evita selecionar o card ao abrir o alerta. */}
                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            className="w-full shrink-0 text-destructive hover:bg-destructive/10 hover:text-destructive sm:w-auto"
                            disabled={marcarNaoAssinatura.isPending}
                            onClick={(e) => e.stopPropagation()}
                            onKeyDown={(e) => e.stopPropagation()}
                          >
                            <Ban className="size-4" /> Não é assinatura
                          </Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>
                              Marcar como não é assinatura?
                            </AlertDialogTitle>
                            <AlertDialogDescription>
                              «{c.nome}» não será mais sugerida como assinatura
                              a partir das suas transações.
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>Cancelar</AlertDialogCancel>
                            <AlertDialogAction
                              className={buttonVariants({
                                variant: "destructive",
                              })}
                              onClick={() =>
                                marcarNaoAssinatura.mutate(c.transacao_ids, {
                                  onSuccess: () =>
                                    toast.success(
                                      `"${c.nome}" não será mais sugerida.`
                                    ),
                                  onError: (err) => toast.error(err.message),
                                })
                              }
                            >
                              Não é assinatura
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    </div>
                  </div>
                </li>
              )
            })}
          </ul>
        )}

        <DialogFooter>
          <DialogClose asChild>
            <Button type="button" variant="outline">
              Cancelar
            </Button>
          </DialogClose>
          <Button
            onClick={adicionar}
            disabled={escolhidas.length === 0 || criarLote.isPending}
          >
            Adicionar selecionadas
            {escolhidas.length ? ` (${escolhidas.length})` : ""}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
