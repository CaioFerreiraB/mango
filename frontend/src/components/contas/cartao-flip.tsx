import { type MouseEvent, useRef } from "react"

import { Bandeira } from "@/components/contas/bandeiras"
import { LogoNubank } from "@/components/contas/logo-nubank"
import type { ContaDetalhe } from "@/lib/api/contas"
import { corDoCartao } from "@/lib/cartao-estilo"
import { iniciais } from "@/lib/format"
import { cn } from "@/lib/utils"

const MODO: Record<string, string> = { CREDIT: "crédito", DEBIT: "débito" }

/** Inclinação máxima (graus) do tilt do cartão ao seguir o cursor. */
const TILT_MAX_DEG = 15

/**
 * Tilt 3D em que o ponto sob o cursor "afunda" (recua para dentro da tela): mouse à direita → lado
 * direito recua (`rotateY` +); mouse em cima → topo recua (`rotateX` +). Retorna graus por eixo.
 */
function tiltFromPointer(rect: DOMRect, clientX: number, clientY: number) {
  const px = (clientX - rect.left) / rect.width - 0.5 // -0.5..0.5
  const py = (clientY - rect.top) / rect.height - 0.5
  return { rx: -py * TILT_MAX_DEG, ry: px * TILT_MAX_DEG }
}

/** 16 posições no formato do cartão: 12 mascaradas + os 4 últimos dígitos reais, em grupos de 4. */
function numeroMascarado(numero?: string | null): string {
  const ult4 = (numero ?? "").replace(/\D/g, "").slice(-4).padStart(4, "•")
  return `•••• •••• •••• ${ult4}`
}

/**
 * Arte grande e interativa do cartão — frente/verso com virada 3D. O cartão inteiro é o botão
 * (clique/teclado); o estado da virada vem do pai para uma segunda affordance ("Virar cartão").
 * Verso é esqueumórfico: `***` (CVV) e `••/••` (validade) são marcadores — o modelo não guarda esses
 * dados; só o titular (`owner`) é real. Cor/skin por `corDoCartao`.
 */
export function CartaoFlip({
  conta,
  nome,
  logoUrl,
  virado,
  onVirar,
}: {
  conta: ContaDetalhe
  nome: string
  logoUrl?: string | null
  virado: boolean
  onVirar: () => void
}) {
  const estilo = corDoCartao(conta.level, conta.marketing_name, nome)
  const ultravioleta = estilo.id === "ultravioleta"
  const face = { background: estilo.fundo, color: estilo.texto }
  const numero = numeroMascarado(conta.numero)
  const nomeFmt = nome.replace(/-/g, " ")
  const modo = MODO[conta.type] ?? null
  const nivel = conta.cartao?.level ?? conta.level ?? null
  const titular = conta.owner?.trim() || null

  const cardRef = useRef<HTMLButtonElement>(null)
  const semMovimento =
    typeof matchMedia !== "undefined" &&
    matchMedia("(prefers-reduced-motion: reduce)").matches

  function aoMover(e: MouseEvent) {
    const el = cardRef.current
    if (!el || semMovimento) return
    const { rx, ry } = tiltFromPointer(
      el.getBoundingClientRect(),
      e.clientX,
      e.clientY
    )
    el.style.transform = `rotateX(${rx}deg) rotateY(${ry}deg)`
  }
  function aoSair() {
    if (cardRef.current) cardRef.current.style.transform = ""
  }

  return (
    <div
      className="mx-auto w-full max-w-sm [perspective:1600px]"
      onMouseMove={aoMover}
      onMouseLeave={aoSair}
    >
      <button
        ref={cardRef}
        type="button"
        onClick={onVirar}
        aria-pressed={virado}
        aria-label={virado ? "Ver a frente do cartão" : "Ver o verso do cartão"}
        className={cn(
          "group relative block aspect-[1.586] w-full cursor-pointer rounded-2xl text-left",
          "shadow-xl transition-transform duration-200 ease-out [perspective:1600px]",
          "will-change-transform motion-reduce:transition-none",
          "focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:outline-none"
        )}
      >
        <div
          className={cn(
            "relative h-full w-full rounded-2xl transition-transform duration-500 ease-out",
            "[transform-style:preserve-3d] motion-reduce:transition-none",
            virado && "[transform:rotateY(180deg)]"
          )}
        >
          {/* Frente */}
          <div
            className="absolute inset-0 overflow-hidden rounded-2xl ring-1 ring-black/10 [-webkit-backface-visibility:hidden] [backface-visibility:hidden]"
            style={face}
          >
            <div
              aria-hidden
              className="pointer-events-none absolute inset-0 bg-gradient-to-tr from-transparent via-white/5 to-white/15"
            />
            <div className="relative flex h-full flex-col justify-between p-5">
              <div className="flex items-start justify-between gap-3">
                {ultravioleta ? (
                  <LogoNubank className="h-11 w-auto" />
                ) : logoUrl ? (
                  <div className="flex size-14 items-center justify-center rounded-full bg-white p-2.5 shadow-sm ring-1 ring-black/5">
                    <img
                      src={logoUrl}
                      alt=""
                      className="max-h-full max-w-full object-contain"
                    />
                  </div>
                ) : (
                  <span className="text-3xl font-bold tracking-tight opacity-95">
                    {iniciais(nome)}
                  </span>
                )}
                <Bandeira
                  brand={conta.brand}
                  prata={ultravioleta}
                  className="h-7 w-auto shrink-0"
                />
              </div>

              <div className="space-y-3">
                <p className="font-mono text-base tracking-[0.14em] tabular-nums">
                  {numero}
                </p>
                <div className="flex items-end justify-between gap-3">
                  <p className="min-w-0 truncate text-sm font-semibold tracking-wide uppercase">
                    {nomeFmt}
                  </p>
                  <div className="shrink-0 text-right leading-tight">
                    {modo ? (
                      <p className="text-xs lowercase opacity-90">{modo}</p>
                    ) : null}
                    {nivel ? (
                      <p className="text-[11px] tracking-[0.2em] uppercase opacity-75">
                        {nivel}
                      </p>
                    ) : null}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Verso */}
          <div
            className="absolute inset-0 [transform:rotateY(180deg)] overflow-hidden rounded-2xl ring-1 ring-black/10 [-webkit-backface-visibility:hidden] [backface-visibility:hidden]"
            style={face}
          >
            <div className="relative flex h-full flex-col">
              {/* tarja preta */}
              <div className="mt-5 h-10 w-full bg-neutral-900" />
              <div className="flex flex-1 flex-col justify-between px-5 pt-4 pb-5">
                {/* tarja branca de assinatura com o código de segurança */}
                <div className="flex h-8 items-center justify-end rounded-sm bg-white px-3">
                  <span className="font-mono text-sm font-semibold tracking-[0.35em] text-neutral-900">
                    ***
                  </span>
                </div>
                <div className="flex items-end justify-between gap-3">
                  <div className="min-w-0 text-left">
                    <p className="text-[10px] tracking-[0.2em] uppercase opacity-70">
                      Titular
                    </p>
                    <p className="truncate text-sm">{titular ?? "—"}</p>
                  </div>
                  <div className="shrink-0 text-right">
                    <p className="text-[10px] tracking-[0.2em] uppercase opacity-70">
                      Válido até
                    </p>
                    {/* ponytail: sem campo de validade no modelo — marcador esqueumórfico */}
                    <p className="font-mono text-sm tabular-nums">••/••</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </button>
    </div>
  )
}
