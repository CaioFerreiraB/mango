import { Bandeira } from "@/components/contas/bandeiras"
import { LogoNubank } from "@/components/contas/logo-nubank"
import type { Conta } from "@/lib/api/contas"
import { corDoCartao } from "@/lib/cartao-estilo"
import { iniciais } from "@/lib/format"
import { cn } from "@/lib/utils"

/** Últimos 4 dígitos no formato pedido `***2425` (o header usa `mascarar`, com bullets). */
function ultimos4(numero?: string | null): string {
  const so = (numero ?? "").replace(/\D/g, "")
  return so ? `***${so.slice(-4)}` : ""
}

/**
 * Arte renderizada do cartão — em pé (retrato), tombada, sangrando no canto do card. Cor pelo
 * tipo/skin, logo grande da instituição no topo-esquerdo e número + bandeira mais abaixo à direita.
 * Decorativa (`aria-hidden`): a identidade textual já vem no header do `ContaCard`.
 */
export function CartaoArt({
  conta,
  nome,
  logoUrl,
  className,
}: {
  conta: Conta
  nome: string
  logoUrl?: string | null
  className?: string
}) {
  const estilo = corDoCartao(conta.level, conta.marketing_name, nome)
  const ultravioleta = estilo.id === "ultravioleta"
  const num = ultimos4(conta.numero)

  return (
    <div
      aria-hidden
      className={cn(
        "pointer-events-none flex aspect-[0.63] w-28 flex-col rounded-xl p-3",
        "shadow-lg ring-1 ring-black/10 transition-transform duration-300",
        "rotate-[6deg] group-hover:rotate-[3deg] group-hover:-translate-y-1",
        className
      )}
      style={{ background: estilo.fundo, color: estilo.texto }}
    >
      {/* topo-esquerdo: logo grande da instituição (direto sobre o cartão) */}
      {ultravioleta ? (
        <LogoNubank className="h-7 w-auto" />
      ) : logoUrl ? (
        <img src={logoUrl} alt="" className="h-8 w-auto max-w-[75%] object-contain" />
      ) : (
        <span className="text-xl font-bold opacity-90">{iniciais(nome)}</span>
      )}

      {/* mais abaixo, à direita: número + bandeira */}
      <div className="mt-6 flex items-center justify-end gap-1.5">
        <span className="font-mono text-[10px] font-medium tabular-nums opacity-95">{num}</span>
        <Bandeira brand={conta.brand} prata={ultravioleta} className="h-4 w-auto shrink-0" />
      </div>
    </div>
  )
}
