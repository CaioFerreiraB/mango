import type { ReactNode } from "react"

/**
 * Cabeçalho de página — o mesmo em todas as telas (DESIGN.md §Anatomia de página): `h1` + uma
 * linha de descrição à esquerda, ações à direita (no máx. uma primária). No mobile as ações ficam
 * na mesma linha do título; botões com rótulo longo usam `<span className="max-sm:sr-only">` e
 * viram só ícone.
 */
export function PageHeader({
  titulo,
  descricao,
  acoes,
}: {
  titulo: ReactNode
  descricao?: ReactNode
  acoes?: ReactNode
}) {
  return (
    // Linha flexível: o título parte do min-content (a palavra mais longa, inteira) e cresce; as
    // ações ficam ao lado enquanto couberem — no celular, na mesma linha do título — e descem
    // para a linha de baixo quando não cabem, sem transbordar. `break-word` (não `anywhere`, que
    // zeraria o min-content) só parte um token maior que a linha inteira. A descrição vem por
    // último, na largura toda (limitada a 70ch).
    <header className="flex flex-wrap items-start gap-x-4 gap-y-1">
      <h1 className="max-w-full min-w-0 grow basis-[min-content] self-center text-[1.625rem] leading-tight font-extrabold tracking-[-0.03em] text-balance [overflow-wrap:break-word] md:text-[1.875rem]">
        {titulo}
      </h1>
      {acoes ? (
        <div className="ml-auto flex flex-wrap items-center justify-end gap-2">
          {acoes}
        </div>
      ) : null}
      {descricao ? (
        // Invólucro na linha inteira (basis-full sozinho, sem max-w, para sempre quebrar linha) e
        // o texto limitado a 70ch dentro dele.
        <div className="mt-0.5 basis-full">
          <div className="max-w-[70ch] text-sm text-pretty text-muted-foreground">
            {descricao}
          </div>
        </div>
      ) : null}
    </header>
  )
}
