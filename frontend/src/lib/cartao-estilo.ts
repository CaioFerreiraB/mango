/**
 * Cor da arte do cartão: identifica o cartão pelo **tipo** (level) e, quando reconhecível, por uma
 * **skin icônica** curada (Nubank roxinho, C6 Carbon…). Cores só inspiradas — não reproduzem a arte
 * oficial (ver `docs/dev/descoberta-saldo-diario-e-imagem-cartao.md`). Cai no **accent do usuário**
 * quando não há tipo nem skin, mantendo a identidade escolhida.
 */

export type CartaoEstilo = {
  /** `background` CSS (gradiente) da face do cartão. */
  fundo: string
  /** Cor do texto/wordmarks sobre o fundo. */
  texto: string
  /** Skin especial reconhecida — só as artes que trocam logo/bandeira usam (ex.: `"ultravioleta"`). */
  id?: string
}

const grad = (a: string, b: string): string => `linear-gradient(135deg, ${a}, ${b})`
const escuro = (a: string, b: string): CartaoEstilo => ({ fundo: grad(a, b), texto: "#ffffff" })
const claro = (a: string, b: string): CartaoEstilo => ({ fundo: grad(a, b), texto: "#161616" })

// Cartões icônicos do Brasil (casados por trecho do nome/marketing_name). Poucos e específicos de
// propósito — falso-positivo é pior que cair no tipo. Ampliar sob demanda.
// Nubank Ultravioleta: violeta com brilho no topo → roxo profundo quase preto. `id` liga o
// tratamento especial das artes (logo "nu" prateado + Mastercard prateada).
const ULTRAVIOLETA: CartaoEstilo = {
  fundo:
    "radial-gradient(125% 120% at 27% 4%, #7d3ac2 0%, #4a1892 32%, #290f5e 60%, #120630 100%)",
  texto: "#f4eefb",
  id: "ultravioleta",
}

const SKINS: Array<{ re: RegExp; estilo: CartaoEstilo }> = [
  { re: /ultraviolet|ultravioleta/, estilo: ULTRAVIOLETA }, // Nubank Ultravioleta
  { re: /nubank|roxinho/, estilo: escuro("#820ad1", "#4a0a78") }, // Nubank roxinho
  { re: /carbon/, estilo: escuro("#2b2b30", "#050506") }, // C6 Carbon
  { re: /\bwill\b/, estilo: claro("#ffe600", "#f2c200") }, // Will Bank
  { re: /\binter\b/, estilo: escuro("#ff7a00", "#c85e00") }, // Inter
  { re: /\bc6\b/, estilo: escuro("#1c1c22", "#050506") }, // C6 padrão
]

const ACCENT: CartaoEstilo = {
  fundo: "linear-gradient(135deg, var(--primary), color-mix(in oklab, var(--primary) 55%, #000))",
  texto: "#ffffff",
}

function porTipo(level: string): CartaoEstilo {
  if (/BLACK|INFINITE/.test(level)) return escuro("#34353b", "#111114")
  if (/PLATINUM|SIGNATURE/.test(level)) return escuro("#6a7079", "#383c43")
  if (/GOLD/.test(level)) return escuro("#c99a3f", "#8a6a1c")
  return ACCENT
}

export function corDoCartao(
  level?: string | null,
  marketingName?: string | null,
  nome?: string | null
): CartaoEstilo {
  // Sandbox/manual nem sempre traz `marketingName` — a identidade do cartão costuma vir no `nome`.
  const alvo = `${marketingName ?? ""} ${nome ?? ""} ${level ?? ""}`.toLowerCase()
  const skin = SKINS.find((s) => s.re.test(alvo))
  return skin ? skin.estilo : porTipo((level ?? "").toUpperCase())
}
