import {
  ArrowRightLeft,
  CalendarCheck,
  CreditCard,
  Repeat,
  StickyNote,
  Users,
} from "lucide-react"
import { useState, type PointerEvent as ReactPointerEvent } from "react"

import { Valor } from "@/components/common/valor"
import { DivisaoDetalheDialog } from "@/components/divisoes/divisao-detalhe-dialog"
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
import { useIconeCategoria } from "@/lib/api/categoria-icones"
import { useContas } from "@/lib/api/contas"
import { usePerfil } from "@/lib/api/perfil"
import {
  descricaoExibida,
  ehLancamento,
  subtituloTransacao,
  valorEfetivoCentavos,
  valorLancamento,
  type DivisaoLancamento,
  type ItemListagem,
  type Transacao,
} from "@/lib/api/transacoes"
import { formatBRL, formatDate } from "@/lib/format"
import { estadoRevisao } from "@/lib/revisao"
import { cn } from "@/lib/utils"

/** Avatar de categoria: fundo tingido suave + ícone colorido, por tipo (entrada/saída). */
function corTile(type: string) {
  return type === "CREDIT"
    ? "bg-positive/15 text-positive-ink"
    : "bg-negative/15 text-negative-ink"
}

/** Marcador de transação dividida: a parte do usuário é o que conta no orçamento. */
function MarcadorDivisao({
  transacao,
  className,
}: {
  transacao: Transacao
  className: string
}) {
  if (!transacao.divisao) return null
  const d = transacao.divisao
  const texto =
    Math.abs(valorEfetivoCentavos(transacao)) === d.valor_total_centavos
      ? `Dividida: sua parte ${formatBRL(d.minha_parte_centavos)} de ${formatBRL(d.valor_total_centavos)}`
      : `Dividida: no orçamento ${formatBRL(d.minha_parte_centavos)} (transação menos ${formatBRL(d.outros_centavos)} da parte dos outros)`
  return (
    <Users className={className} aria-label={texto}>
      <title>{texto}</title>
    </Users>
  )
}

/** Linha secundária de um lançamento de divisão: quem pagou e o que conta para o usuário. */
function subtituloLancamento(l: DivisaoLancamento): string {
  if (l.pendente) return "Você pagou · vincule a transação"
  const parte = `sua parte de ${formatBRL(l.valor_total_centavos)}`
  return l.pago_por_mim
    ? `Você pagou fora do banco · ${parte}`
    : `Pago por ${l.pago_por_nome} · ${parte}`
}

function BadgeLancamento({
  lancamento,
  className,
}: {
  lancamento: DivisaoLancamento
  className?: string
}) {
  if (lancamento.pendente)
    return <StatusBadge estado="pendente" className={className} />
  return (
    <Badge variant="secondary" className={cn("gap-1 font-medium", className)}>
      <Users className="size-3" aria-hidden />
      Dividida
    </Badge>
  )
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
  abrirId = null,
  ocultarCategoria = false,
  parteDoUsuario = false,
  semMoldura = false,
}: {
  items: ItemListagem[]
  /** Repassado ao drawer: esconde "Ir para a fatura" quando já estamos numa fatura. */
  ocultarLinkFatura?: boolean
  /** Transação cujo drawer nasce aberto (link da busca global). */
  abrirId?: number | null
  /** Esconde a coluna Categoria (lista já filtrada por uma categoria — coluna redundante). */
  ocultarCategoria?: boolean
  /** Compra dividida mostra só a parte do usuário (drill-down de gráfico: a lista soma a fatia). */
  parteDoUsuario?: boolean
  /** Sem borda própria: a lista já está dentro de um card (borda dupla = card aninhado). */
  semMoldura?: boolean
}) {
  const valorDe = (t: Transacao) => {
    const v = valorEfetivoCentavos(t)
    return parteDoUsuario && t.divisao
      ? Math.sign(v) * t.divisao.minha_parte_centavos
      : v
  }
  const contas = useContas()
  const contaNome = new Map(
    (contas.data ?? []).map((c) => [
      c.id,
      c.marketing_name ?? c.nome ?? c.pluggy_account_id,
    ])
  )
  const mapaCategorias = useMapaCategorias()
  const iconeCategoria = useIconeCategoria()
  const perfil = usePerfil() // corte da revisão (§4.3) — decide o estado do StatusBadge
  // Descrição · Valor · Data · Conta · Categoria · Status
  const { larguras, iniciar } = useLarguras([300, 120, 110, 160, 180, 120])
  // `abrirId` (busca global → `/transacoes?id=`) só semeia: fechar o drawer não reabre.
  const [selecionadaId, setSelecionadaId] = useState<number | null>(
    abrirId ?? null
  )
  // Com a tabela já montada, um `abrirId` novo (outra busca) abre a transação pedida; fechar o
  // drawer não reabre, porque `abrirId` não muda.
  const [abrirVisto, setAbrirVisto] = useState(abrirId)
  if (abrirId !== abrirVisto) {
    setAbrirVisto(abrirId)
    if (abrirId != null) setSelecionadaId(abrirId)
  }
  const [divisaoId, setDivisaoId] = useState<number | null>(null)
  const selecionada =
    items.find(
      (t): t is Transacao => !ehLancamento(t) && t.id === selecionadaId
    ) ?? null

  return (
    <>
      <div
        className={cn("hidden md:block", !semMoldura && "rounded-lg border")}
      >
        <Table className="table-fixed">
          <colgroup>
            {larguras.map((w, i) =>
              ocultarCategoria && i === 4 ? null : (
                <col key={i} style={{ width: w }} />
              )
            )}
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
              {ocultarCategoria ? null : (
                <TableHead className="relative">
                  Categoria
                  <AlcaResize aoIniciar={iniciar(4)} />
                </TableHead>
              )}
              <TableHead className="text-right">Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((t) => {
              if (ehLancamento(t)) {
                const IconeL = iconeCategoria(t.categoria_id)
                const catL = t.categoria_id
                  ? mapaCategorias.get(t.categoria_id)
                  : undefined
                return (
                  <TableRow
                    key={`d-${t.divisao_id}`}
                    className="cursor-pointer even:bg-muted/40"
                    onClick={() => setDivisaoId(t.divisao_id)}
                  >
                    <TableCell>
                      <div className="flex min-w-0 items-center gap-3">
                        <Avatar className="size-8 shrink-0 after:hidden">
                          <AvatarFallback className={corTile("DEBIT")}>
                            <IconeL className="size-4" aria-hidden />
                          </AvatarFallback>
                        </Avatar>
                        <div className="min-w-0">
                          <button
                            className="flex w-full min-w-0 items-center gap-2 text-left hover:text-primary"
                            onClick={() => setDivisaoId(t.divisao_id)}
                          >
                            <span className="min-w-0 truncate font-medium">
                              {t.descricao ?? "Divisão"}
                            </span>
                            <Users
                              className="size-3.5 shrink-0 text-muted-foreground"
                              aria-label="divisão"
                            />
                          </button>
                          <p className="truncate text-xs text-muted-foreground">
                            {subtituloLancamento(t)}
                          </p>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="truncate">
                        <Valor centavos={valorLancamento(t)} sinal neutro />
                      </div>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      <div className="truncate">{formatDate(t.data)}</div>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      —
                    </TableCell>
                    {ocultarCategoria ? null : (
                      <TableCell>
                        {catL ? (
                          <Badge
                            variant="secondary"
                            className="max-w-full font-normal"
                          >
                            <IconeL className="size-3.5 shrink-0" aria-hidden />
                            <span className="min-w-0 truncate">{catL}</span>
                          </Badge>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </TableCell>
                    )}
                    <TableCell className="text-right">
                      <BadgeLancamento lancamento={t} />
                    </TableCell>
                  </TableRow>
                )
              }
              const catId = t.categoria_efetiva_id
              const catNome = catId ? mapaCategorias.get(catId) : undefined
              const IconeCat = iconeCategoria(catId)
              const titulo = descricaoExibida(t)
              const subtitulo = subtituloTransacao(t)
              return (
                <TableRow
                  key={`t-${t.id}`}
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
                          {t.despesa_fixa_id != null ? (
                            <CalendarCheck
                              className="size-3.5 shrink-0 text-muted-foreground"
                              aria-label="despesa fixa"
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
                          <MarcadorDivisao
                            transacao={t}
                            className="size-3.5 shrink-0 text-muted-foreground"
                          />
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
                      <Valor centavos={valorDe(t)} sinal neutro />
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
                  {ocultarCategoria ? null : (
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
                  )}
                  <TableCell className="text-right">
                    <StatusBadge
                      estado={estadoRevisao(
                        t.revisada,
                        t.date,
                        perfil.data?.revisao_desde
                      )}
                    />
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </div>

      <ul
        className={cn("divide-y md:hidden", !semMoldura && "rounded-lg border")}
      >
        {items.map((t) => {
          if (ehLancamento(t)) {
            const IconeL = iconeCategoria(t.categoria_id)
            return (
              <li key={`d-${t.divisao_id}`}>
                <button
                  className="flex w-full items-center gap-3 px-3 py-3 text-left hover:bg-muted/40"
                  onClick={() => setDivisaoId(t.divisao_id)}
                >
                  <div
                    className={cn(
                      "flex size-10 shrink-0 items-center justify-center rounded-full",
                      corTile("DEBIT")
                    )}
                  >
                    <IconeL className="size-5" aria-hidden />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="flex min-w-0 items-center gap-1.5 text-xs font-semibold">
                      <span className="min-w-0 truncate">
                        {t.descricao ?? "Divisão"}
                      </span>
                      <Users
                        className="size-3 shrink-0 text-muted-foreground"
                        aria-label="divisão"
                      />
                    </p>
                    <p className="truncate text-[11px] text-muted-foreground">
                      {subtituloLancamento(t)}
                    </p>
                    <BadgeLancamento
                      lancamento={t}
                      className="mt-1 px-1.5 py-0 text-[10px]"
                    />
                  </div>
                  <div className="shrink-0 text-right">
                    <Valor
                      centavos={valorLancamento(t)}
                      sinal
                      className="block text-xs font-semibold"
                    />
                    <p className="text-[11px] text-muted-foreground">
                      {formatDate(t.data)}
                    </p>
                  </div>
                </button>
              </li>
            )
          }
          const catId = t.categoria_efetiva_id
          const IconeCat = iconeCategoria(catId)
          const titulo = descricaoExibida(t)
          const subtitulo = subtituloTransacao(t)
          return (
            <li key={`t-${t.id}`}>
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
                    <MarcadorDivisao
                      transacao={t}
                      className="size-3 shrink-0 text-muted-foreground"
                    />
                  </p>
                  {subtitulo ? (
                    <p className="truncate text-[11px] text-muted-foreground">
                      {subtitulo}
                    </p>
                  ) : null}
                  <StatusBadge
                    className="mt-1 px-1.5 py-0 text-[10px]"
                    estado={estadoRevisao(
                      t.revisada,
                      t.date,
                      perfil.data?.revisao_desde
                    )}
                  />
                </div>
                <div className="shrink-0 text-right">
                  <Valor
                    centavos={valorDe(t)}
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
      {divisaoId !== null ? (
        <DivisaoDetalheDialog
          id={divisaoId}
          onClose={() => setDivisaoId(null)}
        />
      ) : null}
    </>
  )
}
