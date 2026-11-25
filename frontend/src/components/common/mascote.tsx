import { useMe } from "@/lib/api/auth"
import { ilustracao, type Cena } from "@/lib/illustrations"
import { cn } from "@/lib/utils"

/** Mascote no avatar escolhido pelo usuário (DESIGN.md §Illustrations). Decoração progressiva:
 *  `alt=""`, a tela funciona sem ele. */
export function Mascote({
  cena,
  className,
}: {
  cena: Cena
  className?: string
}) {
  const me = useMe()
  return (
    <img
      src={ilustracao(me.data?.avatar, cena)}
      alt=""
      aria-hidden
      // Todas as cenas são quadradas: as dimensões reservam a proporção antes do PNG chegar (o
      // tamanho real vem do className).
      width={512}
      height={512}
      draggable={false}
      className={cn(
        "pointer-events-none object-contain select-none",
        className
      )}
    />
  )
}
