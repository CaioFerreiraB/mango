/**
 * Marcas de bandeira compactas e auto-contidas (sem assets externos — CSP-safe, zero deps).
 * Mastercard traz a arte icônica dos dois círculos; as demais usam wordmark em `currentColor`
 * (herda a cor do texto do cartão). Cai no nome cru da bandeira quando não reconhecida.
 */
import { useId } from "react"

function Mastercard({
  className,
  prata,
}: {
  className?: string
  prata?: boolean
}) {
  // Versão "black card": círculos em prata monocromática. `id` único (useId) evita colisão de
  // gradiente quando vários cartões aparecem juntos.
  const g = useId()
  if (prata) {
    return (
      <svg
        viewBox="0 0 48 30"
        className={className}
        role="img"
        aria-label="Mastercard"
      >
        <defs>
          <linearGradient id={g} x1="0" y1="0" x2="0.3" y2="1">
            <stop offset="0" stopColor="#f4f4f7" />
            <stop offset="0.5" stopColor="#c3c3cb" />
            <stop offset="1" stopColor="#9a9aa4" />
          </linearGradient>
        </defs>
        <circle cx="18" cy="15" r="11" fill={`url(#${g})`} />
        <circle cx="30" cy="15" r="11" fill={`url(#${g})`} fillOpacity="0.85" />
        {/* interseção dos dois círculos, um tom mais escuro */}
        <path
          d="M24 6.4a11 11 0 0 1 0 17.2 11 11 0 0 1 0-17.2Z"
          fill="#7f7f88"
        />
      </svg>
    )
  }
  return (
    <svg
      viewBox="0 0 48 30"
      className={className}
      role="img"
      aria-label="Mastercard"
    >
      <circle cx="18" cy="15" r="11" fill="#EB001B" />
      <circle cx="30" cy="15" r="11" fill="#F79E1B" />
      {/* interseção dos dois círculos */}
      <path d="M24 6.4a11 11 0 0 1 0 17.2 11 11 0 0 1 0-17.2Z" fill="#FF5F00" />
    </svg>
  )
}

function Wordmark({
  texto,
  italic,
  className,
}: {
  texto: string
  italic?: boolean
  className?: string
}) {
  return (
    <span
      className={className}
      style={{
        fontStyle: italic ? "italic" : "normal",
        fontWeight: 800,
        letterSpacing: "-0.02em",
        fontSize: "0.875rem",
        lineHeight: 1,
      }}
    >
      {texto}
    </span>
  )
}

/** Bandeira do cartão a partir de `conta.brand`. `null` quando a bandeira é desconhecida/ausente. */
export function Bandeira({
  brand,
  className,
  prata,
}: {
  brand?: string | null
  className?: string
  /** Mastercard prateada (skins "black card", ex.: Ultravioleta). */
  prata?: boolean
}) {
  const b = (brand ?? "").toLowerCase().trim()
  if (!b) return null
  if (b.includes("master"))
    return <Mastercard className={className} prata={prata} />
  if (b.includes("visa"))
    return <Wordmark texto="VISA" italic className={className} />
  if (b.includes("amex") || b.includes("american"))
    return <Wordmark texto="AMEX" className={className} />
  if (b.includes("elo")) return <Wordmark texto="elo" className={className} />
  if (b.includes("hiper"))
    return <Wordmark texto="Hipercard" className={className} />
  if (b.includes("diners"))
    return <Wordmark texto="Diners" className={className} />
  return <Wordmark texto={brand!.toUpperCase()} className={className} />
}
