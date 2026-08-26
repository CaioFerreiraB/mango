import { ArrowRightLeft, CreditCard, Repeat, StickyNote } from "lucide-react"
import { useState, type PointerEvent as ReactPointerEvent } from "react"

import { Valor } from "@/components/common/valor"
import { StatusBadge } from "@/components/transacoes/status-badge"
import { TransacaoDetalhe } from "@/components/transacoes/transacao-detalhe"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { useMapaCategorias } from "@/lib/api/categorias"
import { iconeCategoria } from "@/lib/api/categoria-icones"
import { useContas } from "@/lib/api/contas"
import {
  descricaoExibida,
  subtituloTransacao,
  valorEfetivoCentavos,
  type Transacao,
} from "@/lib/api/transacoes"
import { formatDate } from "@/lib/format"
import { cn } from "@/lib/utils"

/** Avatar de categoria: fundo tingido suave + ícone colorido, por tipo (entrada/saída). */
function corTile(type: string) {
  return type === "CREDIT"
    ? "bg-positive/15 text-positive"
    : "bg-negative/15 text-negative"
}

/** Larguras de coluna arrastáveis (px). Sem persistência — reset ao recarregar. */
function useLarguras(inicial: number[]) {
  const [larguras, setLarguras] = useState(inicial)
  const iniciar = (i: number) => (e: ReactPointerEvent<HTMLElement>) => {
    e.preventDefault()
    e.stopPropagation()
    const th = e.currentTarget.parentElement
    const inicioX = e.clientX
    const inicioW = th ? th.getBoundingClientRect().width : larguras[i]
    const mover = (ev: PointerEvent) => {
      const prox = Math.max(60, inicioW + ev.clientX - inicioX)
      setLarguras((ls) => ls.map((x, j) => (j === i ? prox : x)))
    }
    const soltar = () => {
      document.removeEventListener("pointermove", mover)
      document.removeEventListener("pointerup", soltar)
    }
    document.addEventListener("pointermove", mover)
    document.addEventListener("pointerup", soltar)
  }
  return { larguras, iniciar }
}

function AlcaResize({
  aoIniciar,
}: {
  aoIniciar: (e: ReactPointerEvent<HTMLElement>) => void
}) {
  return (
    <span
      onPointerDown={aoIniciar}
      onClick={(e) => e.stopPropagation()}
      className="absolute top-0 right-0 h-full w-1 cursor-col-resize touch-none select-none hover:bg-border"
      aria-hidden
    />
  )
}

/**
 * Tabela de transações (desktop) + lista em cartões (mobile), com colunas redimensionáveis e
 * drawer de detalhe ao clicar. Reutilizada na listagem de transações e nas compras de uma fatura.
 * `items` é o array vivo da query — a seleção deriva dele para o drawer refletir edições na hora.
 */
export function TransacoesTabela({
  items,
  ocultarLinkFatura = false,
}: {
  items: Transacao[]
  /** Repassado ao drawer: esconde "Ir para a fatura" quando já estamos numa fatura. */
  ocultarLinkFatura?: boolean
}) {
  const contas = useContas()
  const contaNome = new Map(
    (contas.data ?? []).map((c) => [
      c.id,
      c.marketing_name ?? c.nome ?? c.pluggy_account_id,
    ])
  )
  const mapaCategorias = useMapaCategorias()
  // Descrição · Valor · Data · Conta · Categoria · Status
  const { larguras, iniciar } = useLarguras([300, 120, 110, 160, 180, 120])
  const [selecionadaId, setSelecionadaId] = useState<number | null>(null)
  const selecionada = items.find((t) => t.id === selecionadaId) ?? null

  return (
    <>
      <div className="hidden rounded-lg border md:block">
        <Table className="table-fixed">
          <colgroup>
            {larguras.map((w, i) => (
              <col key={i} style={{ width: w }} />
            ))}
          </colgroup>
          <TableHeader>
            <TableRow>
              <TableHead className="relative">
                Descrição
                <AlcaResize aoIniciar={iniciar(0)} />
              </TableHead>
              <TableHead className="relative">
                Valor
                <AlcaResize aoIniciar={iniciar(1)} />
              </TableHead>
              <TableHead className="relative">
                Data
                <AlcaResize aoIniciar={iniciar(2)} />
              </TableHead>
              <TableHead className="relative">
                Conta
                <AlcaResize aoIniciar={iniciar(3)} />
              </TableHead>
              <TableHead className="relative">
                Categoria
                <AlcaResize aoIniciar={iniciar(4)} />
              </TableHead>
              <TableHead className="text-right">Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((t) => {
              const catId = t.categoria_override_id ?? t.categoria_pluggy_id
              const catNome = catId ? mapaCategorias.get(catId) : undefined
              const IconeCat = iconeCategoria(catId)
              const titulo = descricaoExibida(t)
              const subtitulo = subtituloTransacao(t)
              return (
                <TableRow
                  key={t.id}
                  className="cursor-pointer even:bg-muted/40"
                  onClick={() => setSelecionadaId(t.id)}
                >
                  <TableCell>
                    <div className="flex min-w-0 items-center gap-3">
                      <Avatar className="size-8 shrink-0 after:hidden">
                        <AvatarFallback className={corTile(t.type)}>
                          <IconeCat className="size-4" aria-hidden />
                        </AvatarFallback>
                      </Avatar>
                      <div className="min-w-0">
                        <button
                          className="flex w-full min-w-0 items-center gap-2 text-left hover:text-primary"
                          onClick={() => setSelecionadaId(t.id)}
                        >
                          <span
                            className="min-w-0 truncate font-medium"
                            title={titulo ?? undefined}
                          >
                            {titulo ?? "—"}
                          </span>
                          {t.observacoes ? (
                            <StickyNote
                              className="size-3.5 shrink-0 text-muted-foreground"
                              aria-label="tem observações"
                            />
                          ) : null}
                          {t.assinatura_id != null ? (
                            <Repeat
                              className="size-3.5 shrink-0 text-muted-foreground"
                              aria-label="assinatura"
                            />
                          ) : null}
                          {t.eh_transferencia ? (
                            <ArrowRightLeft
                              className="size-3.5 shrink-0 text-muted-foreground"
                              aria-label="transferência"
                            />
                          ) : null}
                          {t.bill_id ? (
                            <CreditCard
                              className="size-3.5 shrink-0 text-muted-foreground"
                              aria-label="na fatura"
                            />
                          ) : null}
                          {t.total_installments ? (
                            <Badge
                              variant="secondary"
                              className="shrink-0 px-1 text-[10px]"
                            >
                              {t.installment_number}/{t.total_installments}
                            </Badge>
                          ) : null}
                        </button>
                        {subtitulo ? (
                          <p
                            className="truncate text-xs text-muted-foreground"
                            title={subtitulo}
                          >
                            {subtitulo}
                          </p>
                        ) : null}
                      </div>
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="truncate">
                      <Valor centavos={valorEfetivoCentavos(t)} sinal neutro />
                    </div>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    <div className="truncate">{formatDate(t.date)}</div>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    <div
                      className="truncate"
                      title={contaNome.get(t.conta_id) ?? undefined}
                    >
                      {contaNome.get(t.conta_id) ?? "—"}
                    </div>
                  </TableCell>
                  <TableCell>
                    {catNome ? (
                      <Badge
                        variant="secondary"
                        className="max-w-full font-normal"
                      >
                        <IconeCat className="size-3.5 shrink-0" aria-hidden />
                        <span className="min-w-0 truncate">{catNome}</span>
                      </Badge>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    <StatusBadge revisada={t.revisada} />
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </div>

      <ul className="divide-y rounded-lg border md:hidden">
        {items.map((t) => {
          const catId = t.categoria_override_id ?? t.categoria_pluggy_id
          const IconeCat = iconeCategoria(catId)
          const titulo = descricaoExibida(t)
          const subtitulo = subtituloTransacao(t)
          return (
            <li key={t.id}>
              <button
                className="flex w-full items-center gap-3 px-3 py-3 text-left hover:bg-muted/40"
                onClick={() => setSelecionadaId(t.id)}
              >
                <div
                  className={cn(
                    "flex size-10 shrink-0 items-center justify-center rounded-full",
                    corTile(t.type)
                  )}
                >
                  <IconeCat className="size-5" aria-hidden />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="flex min-w-0 items-center gap-1.5 text-xs font-semibold">
                    <span className="min-w-0 truncate">{titulo ?? "—"}</span>
                    {t.observacoes ? (
                      <StickyNote
                        className="size-3 shrink-0 text-muted-foreground"
                        aria-label="tem observações"
                      />
                    ) : null}
                  </p>
                  {subtitulo ? (
                    <p className="truncate text-[11px] text-muted-foreground">
                      {subtitulo}
                    </p>
                  ) : null}
                </div>
                <div className="shrink-0 text-right">
                  <Valor
                    centavos={valorEfetivoCentavos(t)}
                    sinal
                    className="block text-xs font-semibold"
                  />
                  <p className="text-[11px] text-muted-foreground">
                    {formatDate(t.date)}
                  </p>
                </div>
              </button>
            </li>
          )
        })}
      </ul>

      <TransacaoDetalhe
        transacao={selecionada}
        onOpenChange={(o) => !o && setSelecionadaId(null)}
        ocultarLinkFatura={ocultarLinkFatura}
      />
    </>
  )
}
