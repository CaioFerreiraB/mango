import { Info, Pencil, PiggyBank, Target, TrendingUp, X, type LucideIcon } from "lucide-react"
import { toast } from "sonner"

import { AnelProgresso } from "@/components/common/anel-progresso"
import { Valor } from "@/components/common/valor"
import { AvatarBanco } from "@/components/contas/avatar-banco"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { Progress } from "@/components/ui/progress"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import { ObjetivoFormDialog } from "@/components/objetivos/objetivo-form-dialog"
import { useIsMobile } from "@/hooks/use-mobile"
import { useContas, type Conta } from "@/lib/api/contas"
import { instituicaoEfetiva, useInstituicoes } from "@/lib/api/instituicoes"
import { useInvestimentos, type Investimento } from "@/lib/api/investimentos"
import {
  useObjetivo,
  useRemoverObjetivo,
  useVincularConta,
  useVincularInvestimento,
  type ObjetivoDetalhe,
  type ObjetivoVinculo,
} from "@/lib/api/objetivos"
import { iconeTipo } from "@/lib/investimento-taxonomia"
import { cn } from "@/lib/utils"

// Subtypes de investimento com ticker próprio (ações, FIIs, ETFs) — mostram o código; os demais
// (renda fixa, previdência…) mostram o ícone do tipo.
const SUBTYPES_COM_TICKER = new Set(["STOCK", "REAL_ESTATE_FUND", "ETF"])

/** Selo com ícone ao lado de um rótulo do painel de estatísticas (layout mobile). */
function IconeStat({ icon: Icone }: { icon: LucideIcon }) {
  return (
    <span
      aria-hidden
      className="grid size-7 shrink-0 place-items-center rounded-md bg-primary/10 text-primary"
    >
      <Icone className="size-3.5" />
    </span>
  )
}

/** "+R$X" em pílula verde quando bateu a meta (com legenda "acima da meta"); senão "faltam R$X" em
 * texto neutro. Compartilhado pelos dois layouts do painel de estatísticas. */
function DeltaMeta({ guardado, alvo }: { guardado: number; alvo: number }) {
  if (guardado >= alvo) {
    return (
      <>
        <Badge variant="positive" className="mt-0.5">
          <Valor centavos={guardado - alvo} sinal neutro />
        </Badge>
        <p className="text-xs text-muted-foreground">acima da meta</p>
      </>
    )
  }
  return (
    <p className="text-xs text-muted-foreground">
      faltam <Valor centavos={alvo - guardado} neutro className="text-xs" />
    </p>
  )
}

/** Quadrado compacto pro ícone de um investimento vinculado: ticker (ações/FIIs/ETFs) ou ícone do
 * tipo (renda fixa…), no mesmo estilo `bg-primary/10` usado na carteira. */
function IconeInvestimento({ investimento }: { investimento: Investimento }) {
  const temTicker = SUBTYPES_COM_TICKER.has(investimento.subtype ?? "")
  const Icone = iconeTipo(investimento.subtype ?? investimento.type)
  return (
    <span
      aria-hidden
      className="grid size-9 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary"
    >
      {temTicker ? (
        <span className="font-mono text-[10px] leading-none font-semibold break-all">
          {investimento.code ?? investimento.nome ?? "?"}
        </span>
      ) : (
        <Icone className="size-4" />
      )}
    </span>
  )
}

/** Linha de uma conta ou investimento vinculado: ícone, nome/tipo, valor, participação % e ação de
 * desvincular. `pctDoTotal` é a fatia do vínculo sobre o total vinculado (não sobre a meta). No
 * mobile a linha quebra em duas (nome/tipo à esquerda; valor+remover e %+barra empilhados à direita)
 * em vez das colunas fixas do desktop, que não cabem numa tela estreita. */
function LinhaVinculo({
  vinculo,
  conta,
  investimento,
  pctDoTotal,
  onRemover,
  isMobile,
}: {
  vinculo: ObjetivoVinculo
  conta?: Conta
  investimento?: Investimento
  pctDoTotal: number
  onRemover: () => void
  isMobile: boolean
}) {
  const instituicoes = useInstituicoes()
  const logoUrl = conta
    ? instituicaoEfetiva(conta, new Map((instituicoes.data ?? []).map((i) => [i.id, i])))
        ?.logo_url
    : undefined
  const nome = vinculo.nome ?? (vinculo.tipo === "conta" ? "Conta" : "Investimento")
  const legenda =
    vinculo.tipo === "conta" ? (conta?.type === "CREDIT" ? "cartão" : "conta") : "investimento"
  const icone =
    vinculo.tipo === "conta" ? (
      <AvatarBanco nome={nome} logoUrl={logoUrl} />
    ) : investimento ? (
      <IconeInvestimento investimento={investimento} />
    ) : (
      <span aria-hidden className="size-9 shrink-0 rounded-lg bg-muted" />
    )

  if (isMobile) {
    return (
      <li className="flex items-start gap-3 py-3">
        {icone}
        <div className="min-w-0 flex-1">
          <p className="text-sm">{nome}</p>
          <p className="text-xs text-muted-foreground">{legenda}</p>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1">
          <div className="flex items-center gap-1">
            <Valor centavos={vinculo.saldo_centavos} neutro className="text-sm" />
            <Button variant="ghost" size="icon-sm" aria-label="Desvincular" onClick={onRemover}>
              <X className="size-3.5" />
            </Button>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-muted-foreground tabular-nums">
              {pctDoTotal.toFixed(1)}%
            </span>
            <Progress value={pctDoTotal} className="h-1.5 w-14" />
          </div>
        </div>
      </li>
    )
  }

  return (
    <li className="flex items-center gap-3 py-2">
      {icone}
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm">
          {nome}
          <span className="ml-2 text-xs text-muted-foreground">{legenda}</span>
        </p>
      </div>
      <div className="w-28 shrink-0 text-right text-sm">
        <Valor centavos={vinculo.saldo_centavos} neutro />
      </div>
      <div className="flex w-24 shrink-0 items-center gap-2">
        <span className="w-10 shrink-0 text-right text-xs text-muted-foreground tabular-nums">
          {pctDoTotal.toFixed(1)}%
        </span>
        <Progress value={pctDoTotal} className="h-1.5" />
      </div>
      <Button variant="ghost" size="icon" aria-label="Desvincular" onClick={onRemover}>
        <X className="size-4" />
      </Button>
    </li>
  )
}

export function ObjetivoDetalheDialog({ id, onClose }: { id: number; onClose: () => void }) {
  const isMobile = useIsMobile()
  const { data, isLoading } = useObjetivo(id)
  const contas = useContas()
  const investimentos = useInvestimentos()
  const vincularConta = useVincularConta()
  const vincularInv = useVincularInvestimento()
  const remover = useRemoverObjetivo()

  const contasPorId = new Map((contas.data ?? []).map((c) => [c.id, c]))
  const investimentosPorId = new Map((investimentos.data ?? []).map((i) => [i.id, i]))

  // Disponíveis para vincular = sem objetivo (a regra 1:1-máx impede roubar de outro objetivo).
  // Cartões (type CREDIT) ficam de fora — objetivo só faz sentido pra saldo guardado, não fatura.
  const contasLivres = (contas.data ?? []).filter(
    (c) => c.objetivo_id == null && c.type !== "CREDIT"
  )
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
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-3xl">
        {isLoading || !data ? (
          <Skeleton className="h-64 w-full" />
        ) : (
          <ObjetivoDetalheConteudo
            data={data}
            isMobile={isMobile}
            contasPorId={contasPorId}
            investimentosPorId={investimentosPorId}
            contasLivres={contasLivres}
            invsLivres={invsLivres}
            onAdicionar={adicionar}
            onDesvincular={(v) =>
              v.tipo === "conta"
                ? vincularConta.mutate({ contaId: v.id, objetivoId: null })
                : vincularInv.mutate({ investimentoId: v.id, objetivoId: null })
            }
            onRemover={() =>
              remover.mutate(id, {
                onSuccess: () => {
                  toast.success("Objetivo removido.")
                  onClose()
                },
                onError: (err) => toast.error(err.message),
              })
            }
            removendo={remover.isPending}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}

function ObjetivoDetalheConteudo({
  data,
  isMobile,
  contasPorId,
  investimentosPorId,
  contasLivres,
  invsLivres,
  onAdicionar,
  onDesvincular,
  onRemover,
  removendo,
}: {
  data: ObjetivoDetalhe
  isMobile: boolean
  contasPorId: Map<number, Conta>
  investimentosPorId: Map<number, Investimento>
  contasLivres: Conta[]
  invsLivres: Investimento[]
  onAdicionar: (valor: string) => void
  onDesvincular: (vinculo: ObjetivoVinculo) => void
  onRemover: () => void
  removendo: boolean
}) {
  const pct = Math.round(data.progresso * 100)
  const total = data.valor_guardado_centavos

  return (
    <>
      <DialogHeader>
        <DialogTitle>Objetivo financeiro</DialogTitle>
      </DialogHeader>

      <div className="space-y-4">
        <div className="flex items-center gap-1.5">
          <p className="text-lg font-semibold">{data.titulo}</p>
          <ObjetivoFormDialog
            objetivo={data}
            trigger={
              <Button variant="ghost" size="icon-sm" aria-label="Editar objetivo">
                <Pencil className="size-3.5" />
              </Button>
            }
          />
        </div>

        <div className="space-y-3 overflow-x-auto rounded-xl border p-4">
          {isMobile ? (
            <div className="flex flex-col items-center gap-4">
              <AnelProgresso pct={pct} />
              <div className="w-full divide-y">
                <div className="flex items-center justify-between gap-3 py-3 first:pt-0">
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <IconeStat icon={Target} />
                    <span>Valor do objetivo</span>
                  </div>
                  <Valor
                    centavos={data.valor_alvo_centavos}
                    neutro
                    className="text-base font-semibold"
                  />
                </div>
                <div className="flex items-center justify-between gap-3 py-3">
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <IconeStat icon={PiggyBank} />
                    <span>Guardado até o momento</span>
                  </div>
                  <Valor
                    centavos={data.valor_guardado_centavos}
                    neutro
                    className="text-base font-semibold"
                  />
                </div>
                <div className="flex items-center justify-between gap-3 py-3 last:pb-0">
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <IconeStat icon={TrendingUp} />
                    <span>% de atingimento</span>
                  </div>
                  <div className="text-right">
                    <p className="text-base font-semibold text-primary tabular-nums">{pct}%</p>
                    <DeltaMeta
                      guardado={data.valor_guardado_centavos}
                      alvo={data.valor_alvo_centavos}
                    />
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex min-w-0 flex-col items-center gap-4 sm:flex-row">
              <AnelProgresso pct={pct} />
              <Separator orientation="vertical" className="hidden self-stretch sm:block" />
              <div className="grid min-w-0 flex-1 grid-cols-3 gap-3">
                <div className="min-w-0">
                  <p className="text-xs text-muted-foreground">Valor do objetivo</p>
                  <Valor centavos={data.valor_alvo_centavos} neutro className="text-base" />
                </div>
                <div className="min-w-0">
                  <p className="text-xs text-muted-foreground">Guardado até o momento</p>
                  <Valor centavos={data.valor_guardado_centavos} neutro className="text-base" />
                </div>
                <div className="min-w-0">
                  <p className="text-xs text-muted-foreground">% de atingimento</p>
                  <p className="text-base font-semibold text-primary tabular-nums">{pct}%</p>
                  <DeltaMeta
                    guardado={data.valor_guardado_centavos}
                    alvo={data.valor_alvo_centavos}
                  />
                </div>
              </div>
            </div>
          )}
          <Progress value={pct} className="h-2.5" />
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between gap-2">
            <Label className="text-xs text-muted-foreground">Contas e investimentos vinculados</Label>
            {contasLivres.length + invsLivres.length > 0 ? (
              <Select onValueChange={onAdicionar} value="">
                <SelectTrigger className="w-auto">
                  <SelectValue
                    placeholder={isMobile ? "Vincular" : "Vincular conta ou investimento"}
                  />
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

          {data.vinculos.length === 0 ? (
            <p className="text-sm text-muted-foreground">Nenhum vínculo ainda.</p>
          ) : (
            <div className="overflow-x-auto">
              <ul className={cn("divide-y", !isMobile && "min-w-fit")}>
                {data.vinculos.map((v) => (
                  <LinhaVinculo
                    key={`${v.tipo}-${v.id}`}
                    vinculo={v}
                    conta={v.tipo === "conta" ? contasPorId.get(v.id) : undefined}
                    investimento={v.tipo === "investimento" ? investimentosPorId.get(v.id) : undefined}
                    pctDoTotal={total > 0 ? (v.saldo_centavos / total) * 100 : 0}
                    onRemover={() => onDesvincular(v)}
                    isMobile={isMobile}
                  />
                ))}
              </ul>
              {isMobile ? (
                <div className="flex items-center justify-between border-t pt-2 font-medium">
                  <span className="text-sm">Total vinculado</span>
                  <div className="flex items-center gap-2 text-sm">
                    <Valor centavos={total} neutro />
                    <span className="text-xs text-muted-foreground">100%</span>
                  </div>
                </div>
              ) : (
                <div className="flex min-w-fit items-center gap-3 border-t pt-2 font-medium">
                  <span className="flex-1 text-sm">Total vinculado</span>
                  <div className="w-28 shrink-0 text-right text-sm">
                    <Valor centavos={total} neutro />
                  </div>
                  <div className="flex w-24 shrink-0 items-center">
                    <span className="w-10 shrink-0 text-right text-xs tabular-nums">100%</span>
                  </div>
                  <span className="size-8" />
                </div>
              )}
            </div>
          )}

          {data.valor_guardado_centavos > data.valor_alvo_centavos ? (
            <div className="flex gap-2 rounded-lg bg-muted/50 p-3 text-sm">
              <Info className="size-4 shrink-0 text-primary" aria-hidden />
              <p className="text-muted-foreground">
                O total vinculado pode ser maior que o objetivo. Você pode manter ou ajustar os
                valores vinculados quando quiser.
              </p>
            </div>
          ) : null}
        </div>

        {data.descricao || data.justificativa ? (
          <div className="space-y-3 border-t pt-4">
            {data.descricao ? (
              <div>
                <p className="text-xs text-muted-foreground">Descrição</p>
                <p className="text-sm">{data.descricao}</p>
              </div>
            ) : null}
            {data.justificativa ? (
              <div>
                <p className="text-xs text-muted-foreground">Justificativa</p>
                <p className="text-sm">{data.justificativa}</p>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>

      <DialogFooter
        className={isMobile ? "flex-col sm:flex-col" : "justify-between sm:justify-between"}
      >
        <Button
          variant={isMobile ? "outline" : "ghost"}
          className="text-destructive"
          disabled={removendo}
          onClick={onRemover}
        >
          Remover objetivo
        </Button>
        <div className="flex gap-2">
          <DialogClose asChild>
            <Button variant="outline" className={isMobile ? "flex-1" : undefined}>
              Cancelar
            </Button>
          </DialogClose>
          <ObjetivoFormDialog
            objetivo={data}
            trigger={<Button className={isMobile ? "flex-1" : undefined}>Editar objetivo</Button>}
          />
        </div>
      </DialogFooter>
    </>
  )
}
