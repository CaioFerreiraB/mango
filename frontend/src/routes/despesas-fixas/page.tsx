import {
  CalendarCheck,
  Check,
  ChevronRight,
  CircleAlert,
  Pause,
  Pencil,
  Play,
  Plus,
  RotateCcw,
  SkipForward,
  Trash2,
} from "lucide-react"
import { useId, useState } from "react"
import { toast } from "sonner"

import { EmptyState } from "@/components/common/empty-state"
import { CurrencyInput } from "@/components/common/currency-input"
import { CardDestaque } from "@/components/common/kpi"
import { PageHeader } from "@/components/common/page-header"
import { Valor } from "@/components/common/valor"
import { BarraMes } from "@/components/despesas-fixas/barra-mes"
import { SituacaoBadge } from "@/components/despesas-fixas/situacao-badge"
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
import {
  Drawer,
  DrawerContent,
  DrawerDescription,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer"
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
import { useIsMobile } from "@/hooks/use-mobile"
import {
  FREQUENCIAS,
  rotuloFrequencia,
  useAtualizarDespesaFixa,
  useAtualizarOcorrencia,
  useCriarDespesaFixa,
  useDespesasFixas,
  useOcorrencias,
  useRemoverDespesaFixa,
  useResumoDespesasFixas,
  type DespesaFixa,
  type DespesaFixaResumo,
  type Frequencia,
  type Ocorrencia,
} from "@/lib/api/despesas-fixas"
import {
  descricaoExibida,
  useTransacoes,
  valorEfetivoCentavos,
} from "@/lib/api/transacoes"
import { formatDataISO, formatDate, formatMesAno, hojeISO } from "@/lib/format"
import { cn } from "@/lib/utils"

/** Sem isto o fim do bottom sheet fica sob a barra de gestos. */
const SAFE_AREA_BOTTOM = "env(safe-area-inset-bottom)"

export function DespesasFixasPage() {
  const despesas = useDespesasFixas()
  const resumo = useResumoDespesasFixas()
  const [abertaId, setAbertaId] = useState<number | null>(null)
  const lista = despesas.data ?? []
  const aberta = lista.find((d) => d.id === abertaId) ?? null

  return (
    <div className="space-y-6">
      <PageHeader
        titulo="Despesas fixas"
        descricao="Contas que se repetem. Marque cada vencimento como pago, ou vincule a transação que o pagou."
        acoes={
          <DespesaFormDialog
            trigger={
              <Button>
                <Plus className="size-4" aria-hidden />
                <span className="max-sm:sr-only">Nova despesa fixa</span>
              </Button>
            }
          />
        }
      />

      {resumo.data?.tem_despesas ? (
        <>
          <CardMes resumo={resumo.data} />
          <CardProximos resumo={resumo.data} onAbrir={setAbertaId} />
        </>
      ) : null}

      {despesas.isError ? (
        <EmptyState title="Não foi possível carregar as despesas fixas" />
      ) : despesas.isLoading ? (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      ) : lista.length === 0 ? (
        <EmptyState
          cena="hang-loose"
          title="Nenhuma despesa fixa"
          description="Cadastre aluguel, condomínio, luz ou parcelas para acompanhar, mês a mês, o que já foi pago e o que está atrasado."
        >
          <DespesaFormDialog
            trigger={
              <Button>
                <Plus className="size-4" /> Nova despesa fixa
              </Button>
            }
          />
        </EmptyState>
      ) : (
        <ul className="space-y-2">
          {lista.map((d) => (
            <li key={d.id}>
              <DespesaRow despesa={d} onAbrir={() => setAbertaId(d.id)} />
            </li>
          ))}
        </ul>
      )}

      <DespesaDetalhe
        despesa={aberta}
        onOpenChange={(v) => !v && setAbertaId(null)}
      />
    </div>
  )
}

function DespesaRow({
  despesa,
  onAbrir,
}: {
  despesa: DespesaFixa
  onAbrir: () => void
}) {
  return (
    <Card
      className={cn(
        "superficie-interativa gap-0 overflow-hidden p-0",
        !despesa.ativa && "opacity-60"
      )}
    >
      <button
        type="button"
        onClick={onAbrir}
        className="flex w-full items-center gap-3 px-4 py-4 text-left"
      >
        <span
          aria-hidden
          className={cn(
            "grid size-11 shrink-0 place-items-center rounded-lg",
            despesa.situacao === "atrasada"
              ? "bg-negative/10 text-negative-ink"
              : "bg-primary/10 text-primary"
          )}
        >
          {despesa.situacao === "atrasada" ? (
            <CircleAlert className="size-5" />
          ) : (
            <CalendarCheck className="size-5" />
          )}
        </span>
        <div className="min-w-0 flex-1 space-y-1">
          <p className="flex flex-wrap items-center gap-x-2 gap-y-1 font-medium">
            <span className="truncate">{despesa.descricao}</span>
            <SituacaoBadge situacao={despesa.situacao} />
            {despesa.qtd_atrasos > 1 ? (
              <Badge
                variant="secondary"
                className="bg-negative/10 text-negative-ink"
              >
                {despesa.qtd_atrasos} atrasos
              </Badge>
            ) : null}
          </p>
          <p className="text-xs text-muted-foreground">
            <Valor centavos={despesa.valor_centavos} neutro /> ·{" "}
            {rotuloFrequencia(despesa.frequencia)}
            {despesa.proximo_vencimento
              ? ` · próximo ${formatDataISO(despesa.proximo_vencimento)}`
              : ""}
            {despesa.fim ? ` · até ${formatDataISO(despesa.fim)}` : ""}
          </p>
        </div>
        <ChevronRight className="size-4 shrink-0 text-muted-foreground" />
      </button>
    </Card>
  )
}

/** Mês corrente: herói com pagas × total, a barra do mês, os valores por estado na própria linha do
 *  herói e o mascote reagindo (assustado com atraso, joinha com tudo pago). */
function CardMes({ resumo }: { resumo: DespesaFixaResumo }) {
  const { pagas, abertas, atrasadas } = resumo
  const total = pagas.qtd + abertas.qtd + atrasadas.qtd
  const cena = atrasadas.qtd
    ? "scared"
    : total && pagas.qtd === total
      ? "thumbs-up"
      : "money"
  const contas = (n: number) => `${n} ${n === 1 ? "conta" : "contas"}`
  return (
    <CardDestaque
      titulo={formatMesAno(`${resumo.mes}-15`).replace(/^./, (c) =>
        c.toUpperCase()
      )}
      valor={
        <>
          {pagas.qtd}{" "}
          <span className="text-lg font-semibold text-muted-foreground">
            de {total} pagas
          </span>
        </>
      }
      mascote={cena}
      estatisticas={[
        {
          rotulo: `Pago · ${contas(pagas.qtd)}`,
          valor: <Valor centavos={pagas.centavos} neutro />,
        },
        {
          rotulo: `Em aberto · ${contas(abertas.qtd)}`,
          valor: <Valor centavos={abertas.centavos} neutro />,
        },
        {
          rotulo: `Atrasado · ${contas(atrasadas.qtd)}`,
          valor: (
            <Valor
              centavos={atrasadas.centavos}
              neutro
              className={cn(atrasadas.qtd > 0 && "text-negative-ink")}
            />
          ),
        },
      ]}
    >
      <div className="max-w-xl">
        <BarraMes resumo={resumo} />
      </div>
    </CardDestaque>
  )
}

function CardProximos({
  resumo,
  onAbrir,
}: {
  resumo: DespesaFixaResumo
  onAbrir: (despesaId: number) => void
}) {
  return (
    <Card>
      <CardHeader className="pb-0">
        <CardTitle>Próximos vencimentos</CardTitle>
      </CardHeader>
      <CardContent>
        {resumo.proximos.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            Nada em aberto. Tudo em dia.
          </p>
        ) : (
          <ul className="divide-y">
            {resumo.proximos.map((p) => (
              <li key={p.ocorrencia_id}>
                <button
                  type="button"
                  onClick={() => onAbrir(p.despesa_id)}
                  className="flex w-full items-center gap-3 rounded-md py-3 text-left transition-colors hover:bg-muted/50"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">
                      {p.descricao}
                    </p>
                    <p
                      className={cn(
                        "text-xs",
                        p.situacao === "atrasada"
                          ? "text-negative-ink"
                          : "text-muted-foreground"
                      )}
                    >
                      {p.situacao === "atrasada" ? "venceu" : "vence"}{" "}
                      {formatDataISO(p.vencimento)}
                    </p>
                  </div>
                  <Valor
                    centavos={p.valor_centavos}
                    neutro
                    className="text-sm font-semibold"
                  />
                  <SituacaoBadge situacao={p.situacao} />
                </button>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}

// --- detalhe ------------------------------------------------------------------------------------

function DespesaDetalhe({
  despesa,
  onOpenChange,
}: {
  despesa: DespesaFixa | null
  onOpenChange: (v: boolean) => void
}) {
  const isMobile = useIsMobile()
  const [editando, setEditando] = useState(false)
  const atualizar = useAtualizarDespesaFixa()
  const d = despesa

  return (
    <>
      <Drawer
        direction={isMobile ? "bottom" : "right"}
        open={d !== null}
        onOpenChange={onOpenChange}
      >
        <DrawerContent
          className="gap-0 overflow-hidden shadow-xl data-[vaul-drawer-direction=bottom]:max-h-[85svh] data-[vaul-drawer-direction=right]:inset-y-2 data-[vaul-drawer-direction=right]:right-2 data-[vaul-drawer-direction=right]:rounded-l-2xl data-[vaul-drawer-direction=right]:rounded-r-2xl data-[vaul-drawer-direction=right]:border data-[vaul-drawer-direction=right]:sm:max-w-md"
          style={{ paddingBottom: isMobile ? SAFE_AREA_BOTTOM : undefined }}
        >
          {d ? (
            // Rolagem no wrapper, nunca no DrawerContent (ver `TransacaoDetalhe`).
            <div className="flex min-h-0 flex-1 flex-col overflow-x-hidden overflow-y-auto">
              <DrawerHeader className="gap-1.5 pt-6 text-left md:text-left">
                <DrawerTitle className="text-lg">{d.descricao}</DrawerTitle>
                <DrawerDescription>
                  <Valor centavos={d.valor_centavos} neutro /> ·{" "}
                  {rotuloFrequencia(d.frequencia)} · dia {d.dia_vencimento}
                  {d.fim ? ` · até ${formatDataISO(d.fim)}` : ""}
                </DrawerDescription>
                <div className="flex flex-wrap items-center gap-2 pt-1">
                  <SituacaoBadge situacao={d.situacao} />
                  {d.qtd_atrasos > 0 ? (
                    <span className="text-xs text-negative-ink">
                      {d.qtd_atrasos}{" "}
                      {d.qtd_atrasos === 1
                        ? "vencimento atrasado"
                        : "vencimentos atrasados"}
                    </span>
                  ) : null}
                  {d.proximo_vencimento ? (
                    <span className="text-xs text-muted-foreground">
                      Próximo: {formatDataISO(d.proximo_vencimento)}
                    </span>
                  ) : null}
                </div>
              </DrawerHeader>
              <div className="space-y-6 px-4 pb-4">
                <Vencimentos despesaId={d.id} />
                <TransacoesVinculadas despesaId={d.id} />
              </div>
              <DrawerFooter className="mt-auto flex-row flex-wrap gap-2 border-t">
                <Button
                  variant="outline"
                  className="flex-1"
                  onClick={() => setEditando(true)}
                >
                  <Pencil className="size-4" /> Editar
                </Button>
                <Button
                  variant="outline"
                  className="flex-1"
                  disabled={atualizar.isPending}
                  onClick={() =>
                    atualizar.mutate(
                      { id: d.id, patch: { ativa: !d.ativa } },
                      {
                        onSuccess: () =>
                          toast.success(
                            d.ativa
                              ? "Despesa desativada: não gera mais vencimentos nem avisos."
                              : "Despesa reativada."
                          ),
                        onError: (err) => toast.error(err.message),
                      }
                    )
                  }
                >
                  {d.ativa ? (
                    <>
                      <Pause className="size-4" /> Desativar
                    </>
                  ) : (
                    <>
                      <Play className="size-4" /> Ativar
                    </>
                  )}
                </Button>
              </DrawerFooter>
            </div>
          ) : null}
        </DrawerContent>
      </Drawer>
      {/* Montado só enquanto edita: cada abertura parte do registro atual, nunca de um rascunho. */}
      {d && editando ? (
        <DespesaFormDialog
          despesa={d}
          open
          onOpenChange={setEditando}
          onExcluida={() => onOpenChange(false)}
        />
      ) : null}
    </>
  )
}

function Vencimentos({ despesaId }: { despesaId: number }) {
  const ocorrencias = useOcorrencias(despesaId)
  return (
    <section className="space-y-2">
      <h3 className="text-sm font-medium">Vencimentos</h3>
      {ocorrencias.isLoading ? (
        <Skeleton className="h-24 w-full" />
      ) : ocorrencias.isError ? (
        <p className="text-sm text-muted-foreground">
          Não foi possível carregar os vencimentos.
        </p>
      ) : !ocorrencias.data?.length ? (
        <p className="text-sm text-muted-foreground">
          Nenhum vencimento até agora.
        </p>
      ) : (
        <ul className="divide-y rounded-lg border">
          {ocorrencias.data.map((o) => (
            <VencimentoItem key={o.id} ocorrencia={o} />
          ))}
        </ul>
      )}
    </section>
  )
}

function VencimentoItem({ ocorrencia: o }: { ocorrencia: Ocorrencia }) {
  const atualizar = useAtualizarOcorrencia()
  const mudar = (status: Ocorrencia["status"], msg: string) =>
    atualizar.mutate(
      { id: o.id, status },
      {
        onSuccess: () => toast.success(msg),
        onError: (err) => toast.error(err.message),
      }
    )
  return (
    <li className="flex flex-wrap items-center gap-x-3 gap-y-2 p-3">
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium">{formatDataISO(o.vencimento)}</p>
        <p className="text-xs text-muted-foreground">
          <Valor centavos={o.valor_centavos} neutro />
          {o.pago_em ? ` · paga em ${formatDataISO(o.pago_em)}` : ""}
          {o.qtd_transacoes
            ? ` · ${o.qtd_transacoes} ${o.qtd_transacoes === 1 ? "transação" : "transações"}`
            : ""}
        </p>
      </div>
      <SituacaoBadge situacao={o.situacao} />
      <div className="flex gap-1">
        {o.status === "aberta" ? (
          <>
            <Button
              size="xs"
              variant="secondary"
              disabled={atualizar.isPending}
              onClick={() => mudar("paga", "Vencimento marcado como pago.")}
            >
              <Check className="size-3.5" /> Pagar
            </Button>
            <Button
              size="xs"
              variant="ghost"
              disabled={atualizar.isPending}
              onClick={() => mudar("pulada", "Vencimento pulado.")}
            >
              <SkipForward className="size-3.5" /> Pular
            </Button>
          </>
        ) : o.qtd_transacoes > 0 ? (
          // Pago por transação: reabrir só desvinculando (a API recusa com 409).
          <span className="text-xs text-muted-foreground">
            Desvincule a transação para reabrir
          </span>
        ) : (
          <Button
            size="xs"
            variant="ghost"
            disabled={atualizar.isPending}
            onClick={() => mudar("aberta", "Vencimento reaberto.")}
          >
            <RotateCcw className="size-3.5" /> Reabrir
          </Button>
        )}
      </div>
    </li>
  )
}

function TransacoesVinculadas({ despesaId }: { despesaId: number }) {
  const transacoes = useTransacoes({ despesa_fixa_id: despesaId, limit: 200 })
  const itens = (transacoes.data?.items ?? []).flatMap((i) =>
    i.origem === "transacao" ? [i] : []
  )
  return (
    <section className="space-y-2">
      <h3 className="text-sm font-medium">Transações vinculadas</h3>
      {transacoes.isLoading ? (
        <Skeleton className="h-16 w-full" />
      ) : transacoes.isError ? (
        <p className="text-sm text-muted-foreground">
          Não foi possível carregar as transações.
        </p>
      ) : itens.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          Nenhuma ainda. Abra uma transação em Transações e escolha esta despesa
          em «É uma despesa fixa».
        </p>
      ) : (
        <ul className="divide-y rounded-lg border">
          {itens.map((t) => (
            <li key={t.id} className="flex items-center gap-3 p-3">
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">
                  {descricaoExibida(t) ?? "Sem descrição"}
                </p>
                <p className="text-xs text-muted-foreground">
                  {formatDate(t.date)}
                </p>
              </div>
              <Valor
                centavos={valorEfetivoCentavos(t)}
                className="text-sm font-semibold"
              />
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

// --- formulário ---------------------------------------------------------------------------------

/** `yyyy-mm-01` do mês corrente (ou do seguinte) no fuso SP. */
function primeiroDoMes(proximo: boolean): string {
  const [ano, mes] = hojeISO().split("-").map(Number)
  const [a, m] = proximo
    ? mes === 12
      ? [ano + 1, 1]
      : [ano, mes + 1]
    : [ano, mes]
  return `${a}-${String(m).padStart(2, "0")}-01`
}

function DespesaFormDialog({
  trigger,
  despesa,
  open,
  onOpenChange,
  onExcluida,
}: {
  trigger?: React.ReactNode
  despesa?: DespesaFixa
  open?: boolean
  onOpenChange?: (v: boolean) => void
  onExcluida?: () => void
}) {
  // Controlado quando `open`/`onOpenChange` vêm de fora; senão, estado interno + trigger.
  const [interno, setInterno] = useState(false)
  const aberto = open ?? interno
  const setAberto = onOpenChange ?? setInterno
  const formId = useId()
  const vazio = {
    descricao: "",
    valor_centavos: 0,
    frequencia: "mensal" as Frequencia,
    dia: "",
    comecaMesAtual: true,
    temporaria: false,
    inicio: hojeISO(),
    fim: "",
    ativa: true,
  }
  const doRegistro = (d: DespesaFixa) => ({
    descricao: d.descricao,
    valor_centavos: d.valor_centavos,
    frequencia: d.frequencia,
    dia: String(d.dia_vencimento),
    comecaMesAtual: true,
    temporaria: d.fim != null,
    inicio: d.inicio,
    fim: d.fim ?? "",
    ativa: d.ativa,
  })
  const [form, setForm] = useState(() =>
    despesa ? doRegistro(despesa) : vazio
  )
  const criar = useCriarDespesaFixa()
  const atualizar = useAtualizarDespesaFixa()
  const remover = useRemoverDespesaFixa()
  const pendente = criar.isPending || atualizar.isPending
  const dia = Number(form.dia)
  const diaValido = Number.isInteger(dia) && dia >= 1 && dia <= 31
  const periodoValido =
    !form.temporaria || (!!form.inicio && !!form.fim && form.fim >= form.inicio)
  const valido =
    form.descricao.trim() !== "" &&
    form.valor_centavos > 0 &&
    diaValido &&
    periodoValido
  const diaJaPassou =
    !despesa &&
    !form.temporaria &&
    form.comecaMesAtual &&
    diaValido &&
    dia < Number(hojeISO().slice(8))

  function trocarAberto(v: boolean) {
    // Recomeça do registro (ou vazio) a cada abertura: cancelar não deixa rascunho para trás.
    if (v) setForm(despesa ? doRegistro(despesa) : vazio)
    setAberto(v)
  }

  function salvar(e: React.FormEvent) {
    e.preventDefault()
    if (!valido) return
    const base = {
      descricao: form.descricao.trim(),
      valor_centavos: form.valor_centavos,
      frequencia: form.frequencia,
      dia_vencimento: dia,
    }
    const onSuccess = () => {
      toast.success(
        despesa ? "Despesa fixa atualizada." : "Despesa fixa criada."
      )
      setAberto(false)
    }
    const onError = (err: Error) => toast.error(err.message)
    if (despesa) {
      // Sem "temporária", a despesa fica permanente (fim nulo); `inicio` só muda se temporária.
      const periodo = form.temporaria
        ? { inicio: form.inicio, fim: form.fim }
        : { fim: null }
      atualizar.mutate(
        { id: despesa.id, patch: { ...base, ...periodo, ativa: form.ativa } },
        { onSuccess, onError }
      )
    } else {
      const periodo = form.temporaria
        ? { inicio: form.inicio, fim: form.fim }
        : { inicio: primeiroDoMes(!form.comecaMesAtual), fim: null }
      criar.mutate({ ...base, ...periodo }, { onSuccess, onError })
    }
  }

  return (
    <Dialog open={aberto} onOpenChange={trocarAberto}>
      {trigger ? <DialogTrigger asChild>{trigger}</DialogTrigger> : null}
      <DialogContent className="flex max-h-[calc(100dvh-2rem)] flex-col gap-0 overflow-hidden p-0 sm:max-w-xl">
        <DialogHeader className="shrink-0 flex-row items-start gap-3 space-y-0 p-4 pr-10">
          <span
            aria-hidden
            className="grid size-11 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary"
          >
            {despesa ? (
              <Pencil className="size-5" />
            ) : (
              <Plus className="size-5" />
            )}
          </span>
          <div className="space-y-1.5">
            <DialogTitle>
              {despesa ? "Editar despesa fixa" : "Nova despesa fixa"}
            </DialogTitle>
            <DialogDescription>
              {despesa
                ? "Mudar valor ou agenda refaz só os vencimentos futuros em aberto."
                : "Uma conta que se repete e você quer acompanhar a cada vencimento."}
            </DialogDescription>
          </div>
        </DialogHeader>
        <form
          id={formId}
          className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4"
          onSubmit={salvar}
        >
          <div className="space-y-1.5">
            <Label htmlFor={`${formId}-descricao`}>Descrição</Label>
            <Input
              id={`${formId}-descricao`}
              value={form.descricao}
              maxLength={255}
              placeholder="Ex.: Aluguel"
              onChange={(e) => setForm({ ...form, descricao: e.target.value })}
              required
            />
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor={`${formId}-valor`}>Valor</Label>
              <CurrencyInput
                id={`${formId}-valor`}
                value={form.valor_centavos}
                onChange={(valor_centavos) =>
                  setForm({ ...form, valor_centavos })
                }
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor={`${formId}-frequencia`}>Frequência</Label>
              <Select
                value={form.frequencia}
                onValueChange={(v) =>
                  setForm({ ...form, frequencia: v as Frequencia })
                }
              >
                <SelectTrigger id={`${formId}-frequencia`} className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {FREQUENCIAS.map((f) => (
                    <SelectItem key={f.value} value={f.value}>
                      {f.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={`${formId}-dia`}>Dia do vencimento</Label>
            <Input
              id={`${formId}-dia`}
              type="number"
              inputMode="numeric"
              min={1}
              max={31}
              value={form.dia}
              aria-describedby={`${formId}-dia-ajuda`}
              aria-invalid={form.dia !== "" && !diaValido}
              onChange={(e) => setForm({ ...form, dia: e.target.value })}
              required
            />
            <p
              id={`${formId}-dia-ajuda`}
              className="text-xs text-muted-foreground"
            >
              {form.frequencia === "semanal" || form.frequencia === "quinzenal"
                ? "Dia do primeiro vencimento; depois, a cada " +
                  (form.frequencia === "semanal" ? "7" : "14") +
                  " dias."
                : "Em meses mais curtos, vence no último dia (ex.: 31 → 28/02)."}
            </p>
          </div>

          {!despesa && !form.temporaria ? (
            <label className="flex items-center justify-between gap-3 rounded-lg border p-3">
              <span>
                <span className="block text-sm font-medium">
                  Começa no mês atual
                </span>
                <span className="block text-xs text-muted-foreground">
                  {diaJaPassou
                    ? "O dia já passou: o vencimento deste mês nasce atrasado. Marque como pago ou pulado depois."
                    : "Desligado, o primeiro vencimento fica para o mês que vem."}
                </span>
              </span>
              <Switch
                checked={form.comecaMesAtual}
                onCheckedChange={(v) => setForm({ ...form, comecaMesAtual: v })}
              />
            </label>
          ) : null}

          <div className="space-y-3 rounded-lg border p-3">
            <label className="flex items-center justify-between gap-3">
              <span>
                <span className="block text-sm font-medium">Temporária</span>
                <span className="block text-xs text-muted-foreground">
                  Tem data para acabar, como um parcelamento.
                </span>
              </span>
              <Switch
                checked={form.temporaria}
                onCheckedChange={(v) => setForm({ ...form, temporaria: v })}
              />
            </label>
            {form.temporaria ? (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label htmlFor={`${formId}-inicio`}>Início</Label>
                  <Input
                    id={`${formId}-inicio`}
                    type="date"
                    value={form.inicio}
                    onChange={(e) =>
                      setForm({ ...form, inicio: e.target.value })
                    }
                    required
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor={`${formId}-fim`}>Término</Label>
                  <Input
                    id={`${formId}-fim`}
                    type="date"
                    min={form.inicio || undefined}
                    value={form.fim}
                    aria-invalid={!!form.fim && form.fim < form.inicio}
                    onChange={(e) => setForm({ ...form, fim: e.target.value })}
                    required
                  />
                </div>
                {form.fim && form.fim < form.inicio ? (
                  <p className="text-xs text-destructive sm:col-span-2">
                    O término deve ser igual ou posterior ao início.
                  </p>
                ) : null}
              </div>
            ) : null}
          </div>

          {despesa ? (
            <label className="flex items-center justify-between gap-3 rounded-lg border p-3">
              <span>
                <span className="block text-sm font-medium">Ativa</span>
                <span className="block text-xs text-muted-foreground">
                  Desativada, não gera vencimentos nem avisos no Telegram. O
                  histórico continua aqui.
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
          {despesa ? (
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
                  <AlertDialogTitle>Excluir despesa fixa?</AlertDialogTitle>
                  <AlertDialogDescription>
                    «{despesa.descricao}» e todo o histórico de vencimentos
                    serão apagados. As transações vinculadas são desvinculadas,
                    mas não apagadas. Para só parar de acompanhar, desative.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancelar</AlertDialogCancel>
                  <AlertDialogAction
                    className={buttonVariants({ variant: "destructive" })}
                    onClick={() =>
                      remover.mutate(despesa.id, {
                        onSuccess: () => {
                          toast.success("Despesa fixa excluída.")
                          setAberto(false)
                          onExcluida?.()
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
            <Button type="submit" form={formId} disabled={!valido || pendente}>
              Salvar
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
