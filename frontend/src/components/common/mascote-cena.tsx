import { Mascote } from "@/components/common/mascote"
import type { Cena } from "@/lib/illustrations"
import { cn } from "@/lib/utils"

/** Curvas de nível (relevo topográfico): 9 anéis irregulares concêntricos em torno de um "pico"
 *  logo abaixo do canto direito. Calculado uma vez — é decoração estática. */
const RELEVO_D = (() => {
  let d = ""
  for (let k = 1; k <= 9; k++) {
    const R = 38 * k
    const pts: string[] = []
    for (let i = 0; i <= 56; i++) {
      const t = (i / 56) * Math.PI * 2
      const r =
        R * (1 + 0.09 * Math.sin(3 * t + k * 0.6) + 0.05 * Math.cos(5 * t - k))
      pts.push(
        `${(470 + r * Math.cos(t)).toFixed(1)} ${(430 + r * Math.sin(t) * 0.8).toFixed(1)}`
      )
    }
    d += `M${pts.join(" L")}Z`
  }
  return d
})()

/** Curvas de nível no accent, ancoradas no canto inferior direito do card (atrás do mascote ou de
 *  outra arte do herói). O card precisa de `relative overflow-hidden`. */
export function Relevo() {
  return (
    <svg
      aria-hidden
      viewBox="0 0 600 400"
      preserveAspectRatio="xMaxYMax slice"
      className="relevo-cena pointer-events-none absolute right-0 bottom-0 z-0 h-full w-[min(42.5rem,100%)]"
    >
      <g className="origin-[78%_100%] animate-[deriva_14s_ease-in-out_infinite] motion-reduce:animate-none">
        <path
          d={RELEVO_D}
          fill="none"
          stroke="var(--grafico-destaque)"
          strokeOpacity={0.3}
          strokeWidth={1.25}
          strokeLinejoin="round"
          vectorEffect="non-scaling-stroke"
        />
      </g>
    </svg>
  )
}

/**
 * O tamanho segue a largura do CARD (container query — o card precisa de `@container`), não a da
 * janela: com sidebar e chat abertos um tablet tem card estreito.
 *
 * Mascote "em cena" no canto inferior direito de um card (DESIGN.md §Illustrations): do tronco
 * para cima, cortado pela borda de baixo (o card precisa de `relative overflow-hidden`), com as
 * curvas de nível no accent atrás. Camadas: relevo (z-0) → mascote (z-[6]) → dados (z-10, com
 * espaço reservado à direita pelo chamador). Entra subindo uma vez; depois fica parado. No celular
 * aparecem só cabeça e tronco (~116px): cabem na faixa do gráfico, abaixo de badges e links.
 */
export function CenaMascote({
  cena,
  tamanho = "grande",
}: {
  cena: Cena
  /** `grande` no herói do Início; `medio` nos heróis das outras telas (cards mais baixos). */
  tamanho?: "grande" | "medio"
}) {
  const grande = tamanho === "grande"
  return (
    <>
      <Relevo />
      <div
        aria-hidden
        className={cn(
          "pointer-events-none absolute right-0 bottom-0 z-[6] size-[10rem] entra",
          grande ? "@xl:size-[13rem] @4xl:size-80" : "@xl:size-[13rem]"
        )}
        style={
          {
            "--dist": "60px",
            "--atraso": "80ms",
            "--dur": "620ms",
          } as React.CSSProperties
        }
      >
        <Mascote
          cena={cena}
          className={cn(
            "absolute -right-14 -bottom-[9.75rem] size-[16rem] max-w-none drop-shadow-[0_14px_20px_rgb(16_24_40/0.16)]",
            grande
              ? "@xl:-right-10 @xl:-bottom-[9.5rem] @xl:size-[21rem] @4xl:-right-6 @4xl:-bottom-[9.375rem] @4xl:size-[26.875rem]"
              : // Médio (heróis das outras telas, ≥ 14rem de altura): ~184px visíveis.
                "@xl:-right-8 @xl:-bottom-[7.5rem] @xl:size-[19rem]"
          )}
        />
      </div>
    </>
  )
}
