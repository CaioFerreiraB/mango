import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"

// Palavras genéricas que não ajudam a formar as iniciais do banco.
const GENERICOS = new Set(["de", "do", "da", "e", "of", "the", "meu", "minha"])

/** Iniciais do banco a partir do nome: 1ª letra das 2 primeiras palavras significativas
 * (ex.: "Nu Pagamentos S.A." → "NP"); com uma só palavra, as 2 primeiras letras. */
function iniciais(nome: string): string {
  const palavras = nome
    .split(/[^\p{L}\p{N}]+/u)
    .filter((p) => p.length > 1 && !GENERICOS.has(p.toLowerCase()))
  if (palavras.length === 0) return "?"
  if (palavras.length === 1) return palavras[0].slice(0, 2).toUpperCase()
  return (palavras[0][0] + palavras[1][0]).toUpperCase()
}

/** Cor de fundo determinística (mesmo nome → mesma cor). L baixo p/ contraste com texto branco. */
function corDeFundo(nome: string): string {
  let h = 0
  for (let i = 0; i < nome.length; i++) h = (h * 31 + nome.charCodeAt(i)) | 0
  return `hsl(${Math.abs(h) % 360} 55% 40%)`
}

/** Logo da instituição quando vinculado (`logoUrl`); senão iniciais+cor derivadas do nome — o
 * connector do sync ("meu Pluggy") não traz logo real. O Radix Avatar cai no fallback se a
 * imagem não carregar. */
export function AvatarBanco({
  nome,
  logoUrl,
}: {
  nome: string
  logoUrl?: string | null
}) {
  return (
    <Avatar aria-hidden className="size-9">
      {logoUrl ? (
        <AvatarImage src={logoUrl} alt="" className="object-contain" />
      ) : null}
      <AvatarFallback
        className="text-xs font-semibold text-white"
        style={{ backgroundColor: corDeFundo(nome) }}
      >
        {iniciais(nome)}
      </AvatarFallback>
    </Avatar>
  )
}
