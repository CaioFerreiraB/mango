import {
  Link2,
  MoreHorizontal,
  Repeat,
  Trash2,
  UserCheck,
  UserX,
  Users,
} from "lucide-react"
import { toast } from "sonner"

import { EmptyState } from "@/components/common/empty-state"
import { CriarUsuarioDialog } from "@/components/configuracoes/criar-usuario-dialog"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Badge } from "@/components/ui/badge"
import { Button, buttonVariants } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  useAtivarUsuarioAdmin,
  useDesativarUsuarioAdmin,
  useMudarTipoUsuarioAdmin,
  useReenviarConviteAdmin,
  useRemoverUsuarioAdmin,
  useUsuariosAdmin,
  type TipoUsuario,
  type UsuarioAdmin,
} from "@/lib/api/usuarios"

/** Aba "Usuários" (§4.11/§5.2), só pro dono da instância: criar (via link, com tipo de acesso),
 *  ativar/desativar e excluir. A criação de usuário saiu do módulo de divisão de contas — lá
 *  agora só resta a lista de "com quem eu divido" (`usePessoasDivisao`), sem gestão. */
export function UsuariosTab() {
  const usuarios = useUsuariosAdmin()

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <CriarUsuarioDialog />
      </div>

      {usuarios.isError ? (
        <EmptyState title="Não foi possível carregar os usuários" />
      ) : usuarios.isLoading ? (
        <Skeleton className="h-48 w-full" />
      ) : (usuarios.data ?? []).length === 0 ? (
        <EmptyState
          icon={Users}
          title="Nenhum usuário ainda"
          description="Crie o primeiro usuário para dar acesso a outra pessoa."
        />
      ) : (
        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Nome</TableHead>
                  <TableHead>E-mail</TableHead>
                  <TableHead>Tipo</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="w-10" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {(usuarios.data ?? []).map((u) => (
                  <LinhaUsuario key={u.id} usuario={u} />
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

function LinhaUsuario({ usuario }: { usuario: UsuarioAdmin }) {
  const ativar = useAtivarUsuarioAdmin()
  const desativar = useDesativarUsuarioAdmin()
  const remover = useRemoverUsuarioAdmin()
  const reenviarConvite = useReenviarConviteAdmin()
  const mudarTipo = useMudarTipoUsuarioAdmin()

  function alternarAtivo() {
    const acao = usuario.ativo ? desativar : ativar
    acao.mutate(usuario.id, {
      onSuccess: () =>
        toast.success(
          usuario.ativo ? "Usuário desativado." : "Usuário reativado."
        ),
      onError: (err) => toast.error(err.message),
    })
  }

  function excluir() {
    remover.mutate(usuario.id, {
      onSuccess: () => toast.success("Usuário excluído."),
      onError: (err) => toast.error(err.message),
    })
  }

  async function copiarNovoLink() {
    reenviarConvite.mutate(usuario.id, {
      onSuccess: async (r) => {
        await navigator.clipboard.writeText(
          `${window.location.origin}${r.link_convite}`
        )
        toast.success(
          "Novo link copiado — o link anterior deixou de funcionar."
        )
      },
      onError: (err) => toast.error(err.message),
    })
  }

  function trocarTipo(tipo: TipoUsuario) {
    if (tipo === usuario.tipo) return
    mudarTipo.mutate(
      { usuarioId: usuario.id, tipo },
      {
        onSuccess: () => toast.success("Tipo de acesso atualizado."),
        onError: (err) => toast.error(err.message),
      }
    )
  }

  return (
    <TableRow>
      <TableCell className="font-medium">{usuario.nome}</TableCell>
      <TableCell className="text-muted-foreground">{usuario.email}</TableCell>
      <TableCell>
        <Badge variant="secondary">
          {usuario.tipo === "completo" ? "Completo" : "Divisão de contas"}
        </Badge>
        {usuario.is_admin ? (
          <Badge variant="outline" className="ml-1.5">
            Administrador
          </Badge>
        ) : null}
      </TableCell>
      <TableCell>
        <Badge variant={usuario.ativo ? "secondary" : "outline"}>
          {!usuario.ativo
            ? "Desativado"
            : usuario.status === "so_divisao"
              ? "Convite pendente"
              : "Ativo"}
        </Badge>
      </TableCell>
      <TableCell>
        {usuario.is_admin ? null : (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="icon-sm"
                aria-label={`Ações para ${usuario.nome}`}
              >
                <MoreHorizontal className="size-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {usuario.status === "so_divisao" ? (
                <DropdownMenuItem onSelect={copiarNovoLink}>
                  <Link2 className="size-4" /> Copiar novo link
                </DropdownMenuItem>
              ) : null}
              <DropdownMenuSub>
                <DropdownMenuSubTrigger>
                  <Repeat className="size-4" /> Trocar tipo
                </DropdownMenuSubTrigger>
                <DropdownMenuSubContent>
                  <DropdownMenuRadioGroup
                    value={usuario.tipo}
                    onValueChange={(v) => trocarTipo(v as TipoUsuario)}
                  >
                    <DropdownMenuRadioItem value="completo">
                      Completo
                    </DropdownMenuRadioItem>
                    <DropdownMenuRadioItem value="divisao">
                      Divisão de contas
                    </DropdownMenuRadioItem>
                  </DropdownMenuRadioGroup>
                </DropdownMenuSubContent>
              </DropdownMenuSub>
              <DropdownMenuSeparator />
              <DropdownMenuItem onSelect={alternarAtivo}>
                {usuario.ativo ? (
                  <>
                    <UserX className="size-4" /> Desativar
                  </>
                ) : (
                  <>
                    <UserCheck className="size-4" /> Ativar
                  </>
                )}
              </DropdownMenuItem>
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <DropdownMenuItem
                    variant="destructive"
                    onSelect={(e) => e.preventDefault()}
                  >
                    <Trash2 className="size-4" /> Excluir
                  </DropdownMenuItem>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>Excluir usuário</AlertDialogTitle>
                    <AlertDialogDescription>
                      Tem certeza que deseja excluir "{usuario.nome}"? Se a
                      conta já tiver dados vinculados (transações, divisões de
                      conta…), desative em vez de excluir.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Cancelar</AlertDialogCancel>
                    <AlertDialogAction
                      className={buttonVariants({ variant: "destructive" })}
                      onClick={excluir}
                    >
                      Excluir
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </TableCell>
    </TableRow>
  )
}
