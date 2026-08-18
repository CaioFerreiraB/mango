import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { iniciais } from "@/lib/format"
import { ilustracao } from "@/lib/illustrations"
import { cn } from "@/lib/utils"

/** Avatar de uma pessoa (contraparte de divisão) — iniciais como fallback, mesmo padrão de
 *  `nav-user.tsx`. Diferente da ilustração-mascote (`ilustracao`): aqui é sempre "outra pessoa". */
export function PessoaAvatar({
  nome,
  avatar,
  className,
}: {
  nome: string
  avatar: number | null
  className?: string
}) {
  return (
    <Avatar className={cn("size-9 rounded-full", className)}>
      <AvatarImage src={ilustracao(avatar, "default")} alt="" />
      <AvatarFallback className="rounded-full">{iniciais(nome)}</AvatarFallback>
    </Avatar>
  )
}
