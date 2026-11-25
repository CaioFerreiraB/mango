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
    // Grade: título | ações na 1ª linha; a descrição desce para a largura toda no celular (não
    // fica espremida ao lado dos botões) e volta para baixo do título a partir de `sm`.
    <header className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-x-4 gap-y-1">
      <h1 className="col-start-1 row-start-1 self-center text-xl font-semibold tracking-tight text-balance">
        {titulo}
      </h1>
      {acoes ? (
        <div className="col-start-2 row-start-1 flex flex-wrap items-center justify-end gap-2 sm:row-span-2">
          {acoes}
        </div>
      ) : null}
      {descricao ? (
        <div className="col-span-2 row-start-2 max-w-[70ch] text-sm text-pretty text-muted-foreground sm:col-span-1">
          {descricao}
        </div>
      ) : null}
    </header>
  )
}
