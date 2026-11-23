import { ChevronRight, PanelLeft } from "lucide-react"
import { Fragment, useEffect } from "react"
import { NavLink, useLocation } from "react-router"

import { NavUser } from "@/components/layout/nav-user"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  SidebarRail,
  SidebarSeparator,
  useSidebar,
} from "@/components/ui/sidebar"
import {
  dashboardItem,
  investimentosSection,
  isActivePath,
  navSections,
  navSectionsDivisaoOnly,
  settingsItem,
} from "@/config/nav"
import { useMe } from "@/lib/api/auth"

/** Item de nível superior sem filhos (Dashboard, Configurações). */
function NavItemButton({
  item,
  pathname,
}: {
  item: typeof dashboardItem
  pathname: string
}) {
  return (
    <SidebarMenuItem>
      <SidebarMenuButton
        asChild
        isActive={isActivePath(pathname, item.url)}
        tooltip={item.title}
      >
        <NavLink to={item.url}>
          <item.icon aria-hidden />
          <span>{item.title}</span>
        </NavLink>
      </SidebarMenuButton>
    </SidebarMenuItem>
  )
}

/** Seção com subitens: colapsada (só ícones) abre um dropdown; expandida usa o Collapsible. */
function NavSectionItem({
  section,
  pathname,
}: {
  section: (typeof navSections)[number]
  pathname: string
}) {
  const { state, isMobile } = useSidebar()
  const temFilhoAtivo = section.items.some((item) =>
    isActivePath(pathname, item.url)
  )

  // Colapsada no desktop não há espaço para os subitens: mostra-os num dropdown.
  if (state === "collapsed" && !isMobile) {
    return (
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton isActive={temFilhoAtivo}>
              <section.icon aria-hidden />
              <span>{section.label}</span>
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent side="right" align="start" className="min-w-48">
            <DropdownMenuLabel>{section.label}</DropdownMenuLabel>
            {section.items.map((item) => (
              <DropdownMenuItem key={item.url} asChild>
                <NavLink
                  to={item.url}
                  className={
                    isActivePath(pathname, item.url) ? "font-medium" : undefined
                  }
                >
                  <item.icon aria-hidden />
                  <span>{item.title}</span>
                </NavLink>
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    )
  }

  return (
    <Collapsible
      asChild
      defaultOpen={temFilhoAtivo}
      className="group/collapsible"
    >
      <SidebarMenuItem>
        <CollapsibleTrigger asChild>
          <SidebarMenuButton tooltip={section.label}>
            <section.icon aria-hidden />
            <span>{section.label}</span>
            <ChevronRight
              className="ml-auto transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90 motion-reduce:transition-none"
              aria-hidden
            />
          </SidebarMenuButton>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <SidebarMenuSub>
            {section.items.map((item) => (
              <SidebarMenuSubItem key={item.url}>
                <SidebarMenuSubButton
                  asChild
                  isActive={isActivePath(pathname, item.url)}
                >
                  <NavLink to={item.url}>
                    <item.icon aria-hidden />
                    <span>{item.title}</span>
                  </NavLink>
                </SidebarMenuSubButton>
              </SidebarMenuSubItem>
            ))}
          </SidebarMenuSub>
        </CollapsibleContent>
      </SidebarMenuItem>
    </Collapsible>
  )
}

/** Recolhe/expande a barra (atalho Ctrl+B). Recolhida, mostra só o ícone com a dica. */
function BotaoRecolher() {
  const { state, toggleSidebar } = useSidebar()
  const rotulo = state === "collapsed" ? "Expandir menu" : "Recolher menu"
  return (
    <SidebarMenuItem>
      <SidebarMenuButton
        onClick={toggleSidebar}
        tooltip={`${rotulo} (Ctrl+B)`}
        aria-label={rotulo}
      >
        <PanelLeft aria-hidden />
        <span>{rotulo}</span>
      </SidebarMenuButton>
    </SidebarMenuItem>
  )
}

export function AppSidebar() {
  const { pathname } = useLocation()
  const me = useMe()
  // Conta "divisao" (§4.11) só enxerga o módulo de divisão de contas — Dashboard e Investimentos
  // somem, e a única seção vira "Compartilhado" (Configurações continua pros dois tipos).
  const somenteDivisao = me.data?.tipo === "divisao"
  const secoes = somenteDivisao ? navSectionsDivisaoOnly : navSections
  const { isMobile, setOpenMobile } = useSidebar()
  // Mobile (gaveta): ir para outra rota — por qualquer link do menu — fecha a gaveta.
  useEffect(() => setOpenMobile(false), [pathname, setOpenMobile])

  return (
    <Sidebar variant="inset" collapsible="icon">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild tooltip="mango">
              <NavLink to="/">
                <img
                  src="/illustrations/avatars/logo/mango-logo.png"
                  alt=""
                  className="size-8 shrink-0 object-contain"
                />
                <span className="text-base font-semibold tracking-tight">
                  mango
                </span>
              </NavLink>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      {/* Mobile (gaveta de toque): linhas de 44px e texto maior, em vez das de 32px do desktop. */}
      <SidebarContent
        className={
          isMobile
            ? "[&_[data-sidebar=menu-button]]:h-11 [&_[data-sidebar=menu-button]]:text-[15px] [&_[data-sidebar=menu-sub-button]]:h-10 [&_[data-sidebar=menu-sub-button]]:text-[15px]"
            : undefined
        }
      >
        <SidebarGroup>
          <SidebarGroupContent>
            {/* Recolher/expandir como 1ª linha da navegação, separada do resto por uma linha. No
                mobile o menu é uma gaveta (fecha tocando fora/Esc), então não há o que recolher. */}
            {isMobile ? null : (
              <>
                <SidebarMenu>
                  <BotaoRecolher />
                </SidebarMenu>
                {/* Recolhida, os botões são `size-8` alinhados à esquerda: a linha acompanha. */}
                <SidebarSeparator className="my-2 group-data-[collapsible=icon]:mx-0 group-data-[collapsible=icon]:w-8!" />
              </>
            )}
            <SidebarMenu>
              {!somenteDivisao && (
                <NavItemButton item={dashboardItem} pathname={pathname} />
              )}

              {/* Investimentos (seção) fica logo após Planejamento, antes de Compartilhado. */}
              {secoes.map((section) => (
                <Fragment key={section.label}>
                  <NavSectionItem section={section} pathname={pathname} />
                  {!somenteDivisao && section.label === "Planejamento" ? (
                    <NavSectionItem
                      section={investimentosSection}
                      pathname={pathname}
                    />
                  ) : null}
                </Fragment>
              ))}

              <NavItemButton item={settingsItem} pathname={pathname} />
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter>
        <NavUser />
      </SidebarFooter>

      <SidebarRail />
    </Sidebar>
  )
}
