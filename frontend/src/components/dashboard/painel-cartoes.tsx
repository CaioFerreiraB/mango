import { ChevronDown } from "lucide-react"
import { useState } from "react"
import { Link } from "react-router"

import { Valor } from "@/components/common/valor"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { useCartoesPainel, type CartoesResumo } from "@/lib/api/dashboard"
import { formatBucketLabel, formatMesAno, hojeISO } from "@/lib/format"
import { cn } from "@/lib/utils"

type Cartao = CartoesResumo["cartoes"][number]

const ddmm = (iso: string) => {
  const [, m, d] = iso.split("-")
  return `${d}/${m}`
}

// Identidade do cartão pela paleta categórica (ordem fixa); da 9ª em diante, neutro.
const corCartao = (i: number) =>
  i < 8 ? `var(--chart-cat-${i + 1})` : "var(--chart-cat-outras)"

/**
 * Painel dos cartões (visão global + um bloco por cartão). Compras = compras no cartão no mês;
 * fatura atual = saldo do cartão; próximas = parcelas e compras com data futura. A barra mostra o
 * limite comprometido: fatura atual (accent) + próximas (accent claro).
 */
export function PainelCartoes({
  saidasMes,
}: {
  saidasMes: number | undefined
}) {
  const q = useCartoesPainel()
  const [recolhido, setRecolhido] = useState(true)

  if (q.isLoading) return <Skeleton className="h-40 w-full" />
  if (q.isError || !q.data)
    return (
      <p className="py-4 text-sm text-muted-foreground">
        Não foi possível carregar os cartões.
      </p>
    )
  const r = q.data
  if (r.cartoes.length === 0)
    return (
      <p className="py-4 text-sm text-muted-foreground">
        Nenhum cartão de crédito conectado.
      </p>
    )

  const hoje = hojeISO()
  const janela = `${formatBucketLabel(`${hoje.slice(0, 4)}-01-01`, "mensal")} a ${formatBucketLabel(hoje, "mensal")}`
  const pctGastos =
    saidasMes && saidasMes > 0
      ? Math.round((r.compras_mes_centavos / saidasMes) * 100)
      : null

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 text-xs text-muted-foreground">
        <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span>Compras de {formatMesAno(`${hoje}T12:00:00`)}</span>
          <span className="flex items-center gap-1.5">
            <span className="size-2.5 rounded-[2px] bg-primary" aria-hidden />
            fatura atual
          </span>
          <span className="flex items-center gap-1.5">
            <span
              className="size-2.5 rounded-[2px] bg-primary/35"
              aria-hidden
            />
            próximas faturas
          </span>
        </span>
        <Button
          variant="ghost"
          size="sm"
          className="-my-1 h-7"
          aria-expanded={!recolhido}
          onClick={() => setRecolhido((v) => !v)}
        >
          <ChevronDown
            className={cn(
              "transition-transform duration-200",
              recolhido && "-rotate-90"
            )}
            aria-hidden
          />
          {recolhido ? "Mostrar cartões" : "Recolher cartões"}
        </Button>
      </div>

      <div className="grid grid-cols-2 gap-3 @xl:grid-cols-3 @4xl:grid-cols-5">
        <Resumo
          rotulo="Compras no mês"
          centavos={r.compras_mes_centavos}
          detalhe={pctGastos != null ? `${pctGastos}% dos gastos` : undefined}
          destaque
        />
        <Resumo
          rotulo="Fatura atual"
          centavos={r.fatura_atual_centavos}
          detalhe={`${r.cartoes.length} ${r.cartoes.length === 1 ? "cartão" : "cartões"}`}
        />
        <Resumo
          rotulo="Próximas faturas"
          centavos={r.proximas_centavos}
          detalhe="parcelas e compras futuras"
          destaque
        />
        <Resumo
          rotulo="Total gasto no ano"
          centavos={r.total_ano_centavos}
          detalhe={`${janela} nos cartões`}
        />
        <Resumo
          rotulo="Média por mês"
          centavos={r.media_mes_centavos}
          detalhe={janela}
          destaque
        />
      </div>

      {recolhido ? null : (
        <div className="grid gap-3 @3xl:grid-cols-2">
          {r.cartoes.map((c, i) => (
            <BlocoCartao key={c.conta_id} c={c} cor={corCartao(i)} />
          ))}
        </div>
      )}
    </div>
  )
}

function Resumo({
  rotulo,
  centavos,
  detalhe,
  destaque = false,
}: {
  rotulo: string
  centavos: number
  detalhe?: string
  destaque?: boolean
}) {
  return (
    <div className="min-w-0 rounded-lg bg-muted/50 px-3 py-2.5">
      <p className="truncate text-xs text-muted-foreground">{rotulo}</p>
      <Valor
        centavos={centavos}
        neutro
        className={cn(
          "block truncate text-base font-semibold",
          destaque && "text-accent-ink"
        )}
      />
      {detalhe ? (
        <p className="truncate text-xs text-muted-foreground">{detalhe}</p>
      ) : null}
    </div>
  )
}

function BlocoCartao({ c, cor }: { c: Cartao; cor: string }) {
  const limite = c.limite_centavos
  // Comprometido: o que o banco diz (limite − disponível); sem disponível, fatura + próximas.
  const usado =
    limite != null && c.disponivel_centavos != null
      ? limite - c.disponivel_centavos
      : c.fatura_atual_centavos + c.proximas_centavos
  const pct = (v: number) =>
    limite ? Math.min(100, Math.max(0, (v / limite) * 100)) : 0
  const pctFatura = pct(c.fatura_atual_centavos)
  const pctProximas = Math.min(100 - pctFatura, pct(c.proximas_centavos))
  const datas = [
    c.fecha ? `fecha ${ddmm(c.fecha)}` : null,
    c.vence
      ? c.fecha
        ? `vence ${ddmm(c.vence)}`
        : `vence dia ${Number(c.vence.slice(8))}`
      : null,
  ].filter(Boolean)

  return (
    <div className="space-y-3 rounded-lg border p-4">
      <div className="flex items-baseline justify-between gap-3">
        <Link
          to={`/contas/${c.conta_id}`}
          className="flex min-w-0 items-center gap-2 font-medium hover:underline"
        >
          <span
            className="size-2.5 shrink-0 rounded-full"
            style={{ background: cor }}
            aria-hidden
          />
          <span className="truncate">{c.nome}</span>
        </Link>
        {datas.length ? (
          <span className="shrink-0 text-xs text-muted-foreground">
            {datas.join(" · ")}
          </span>
        ) : null}
      </div>

      {limite ? (
        <div className="space-y-1.5">
          <div
            className="flex h-2 overflow-hidden rounded-full bg-muted"
            role="img"
            aria-label={`${Math.round(pct(usado))}% do limite comprometido`}
          >
            <div
              className="h-full bg-primary"
              style={{ width: `${pctFatura}%` }}
            />
            <div
              className="h-full bg-primary/35"
              style={{ width: `${pctProximas}%` }}
            />
          </div>
          <div className="flex justify-between gap-3 text-xs text-muted-foreground">
            <span>{Math.round(pct(usado))}% do limite comprometido</span>
            <span>
              Limite <Valor centavos={limite} neutro />
            </span>
          </div>
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">Limite não informado.</p>
      )}

      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm @lg:grid-cols-4">
        <Item
          rotulo="Compras no mês"
          centavos={c.compras_mes_centavos}
          destaque
        />
        <Item rotulo="Fatura atual" centavos={c.fatura_atual_centavos} />
        <Item rotulo="Próximas" centavos={c.proximas_centavos} destaque />
        {c.disponivel_centavos != null ? (
          <Item rotulo="Disponível" centavos={c.disponivel_centavos} />
        ) : null}
      </dl>
    </div>
  )
}

function Item({
  rotulo,
  centavos,
  destaque = false,
}: {
  rotulo: string
  centavos: number
  destaque?: boolean
}) {
  return (
    <div className="min-w-0">
      <dt className="truncate text-xs text-muted-foreground">{rotulo}</dt>
      <dd>
        <Valor
          centavos={centavos}
          neutro
          className={cn("font-semibold", destaque && "text-accent-ink")}
        />
      </dd>
    </div>
  )
}
