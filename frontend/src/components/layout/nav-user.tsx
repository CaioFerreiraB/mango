import { useQueryClient } from "@tanstack/react-query"
import { Check, ChevronsUpDown, LogOut, Moon, Sun } from "lucide-react"
import { useNavigate } from "react-router"

import { useTheme } from "@/components/theme-provider"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar"
import { authKeys, useMe, useSetupStatus } from "@/lib/api/auth"
import { api } from "@/lib/api/client"
import { iniciais } from "@/lib/format"
import { ilustracao } from "@/lib/illustrations"
import { cn } from "@/lib/utils"

/** Só Claro/Escuro (decisão do produto); "Sistema" fica de fora do menu do usuário. */
const THEME_OPTIONS = [
  { value: "light", label: "Claro", icon: Sun },
  { value: "dark", label: "Escuro", icon: Moon },
] as const

/** Botão de usuário fixo no rodapé: nome/email, alternância de tema e logout (self-hosted). */
export function NavUser() {
  const { isMobile } = useSidebar()
  const { theme, setTheme } = useTheme()
  const me = useMe()
  const status = useSetupStatus()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const nome = me.data?.nome ?? "Conta"
  const email = me.data?.email ?? ""
  const avatarSrc = ilustracao(me.data?.avatar, "default")
  const podeSair = status.data?.app_mode === "self_hosted"

  async function sair() {
    await api.POST("/api/auth/logout")
    await queryClient.invalidateQueries({ queryKey: authKeys.me })
    navigate("/login", { replace: true })
  }

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton
              size="lg"
              className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
            >
              <Avatar className="size-8 rounded-lg">
                <AvatarImage src={avatarSrc} alt="" />
                <AvatarFallback className="rounded-lg">
                  {iniciais(nome)}
                </AvatarFallback>
              </Avatar>
              <div className="grid flex-1 text-left text-sm leading-tight">
                <span className="truncate font-medium">{nome}</span>
                <span className="truncate text-xs text-muted-foreground">
                  {email}
                </span>
              </div>
              <ChevronsUpDown className="ml-auto size-4" aria-hidden />
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            className="w-(--radix-dropdown-menu-trigger-width) min-w-56 rounded-lg"
            side={isMobile ? "bottom" : "right"}
            align="end"
            sideOffset={4}
          >
            <DropdownMenuLabel className="p-0 font-normal">
              <div className="flex items-center gap-2 px-1 py-1.5 text-left text-sm">
                <Avatar className="size-8 rounded-lg">
                  <AvatarImage src={avatarSrc} alt="" />
                  <AvatarFallback className="rounded-lg">
                    {iniciais(nome)}
                  </AvatarFallback>
                </Avatar>
                <div className="grid flex-1 text-left text-sm leading-tight">
                  <span className="truncate font-medium">{nome}</span>
                  <span className="truncate text-xs text-muted-foreground">
                    {email}
                  </span>
                </div>
              </div>
            </DropdownMenuLabel>

            <DropdownMenuSeparator />
            <DropdownMenuLabel className="text-xs text-muted-foreground">
              Tema
            </DropdownMenuLabel>
            <DropdownMenuGroup>
              {THEME_OPTIONS.map((opt) => (
                <DropdownMenuItem
                  key={opt.value}
                  onClick={() => setTheme(opt.value)}
                >
                  <opt.icon aria-hidden />
                  <span>{opt.label}</span>
                  <Check
                    className={cn(
                      "ml-auto",
                      theme === opt.value ? "opacity-100" : "opacity-0"
                    )}
                    aria-hidden
                  />
                </DropdownMenuItem>
              ))}
            </DropdownMenuGroup>

            {podeSair ? (
              <>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={sair}>
                  <LogOut aria-hidden />
                  <span>Sair</span>
                </DropdownMenuItem>
              </>
            ) : null}
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}
