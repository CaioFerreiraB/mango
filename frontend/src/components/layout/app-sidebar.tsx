import { ChevronRight, PanelLeft } from "lucide-react"
import { Fragment, useEffect, useLayoutEffect, useRef, useState } from "react"
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
  useSidebar,
} from "@/components/ui/sidebar"
import {
  dashboardItem,
  inicioItem,
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
  const [aberta, setAberta] = useState(temFilhoAtivo)

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
      open={aberta}
      onOpenChange={setAberta}
      className="group/collapsible"
    >
      <SidebarMenuItem>
        <CollapsibleTrigger asChild>
          {/* Fechada com a página atual dentro, a seção é quem fica "ativa" (a pílula pousa nela). */}
          <SidebarMenuButton
            tooltip={section.label}
            isActive={temFilhoAtivo && !aberta}
          >
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

/** Escrita de estilo fora do hook (o lint de imutabilidade não aceita mutar o que veio de ref). */
function posicionarPilula(pilula: HTMLElement, nav: HTMLElement) {
  // O ativo mais profundo e visível (subitem dentro da seção aberta > seção recolhida).
  const ativos = [
    ...nav.querySelectorAll<HTMLElement>(
      '[data-sidebar="menu-button"][data-active="true"], [data-sidebar="menu-sub-button"][data-active="true"]'
    ),
  ].filter((e) => e.offsetParent !== null && e.offsetHeight > 0)
  const alvo = ativos.at(-1)
  if (!alvo) {
    pilula.style.opacity = "0"
    return
  }
  const n = nav.getBoundingClientRect()
  const a = alvo.getBoundingClientRect()
  pilula.style.opacity = "1"
  pilula.style.width = `${a.width}px`
  pilula.style.height = `${a.height}px`
  pilula.style.transform = `translate(${a.left - n.left}px, ${a.top - n.top}px)`
}
function marcarPronta(pilula: HTMLElement) {
  pilula.dataset.pronto = ""
}

/** Mantém a pílula sobre o item ativo: re-mede na troca de rota/estado, quando uma seção abre ou
 *  fecha (o ResizeObserver acompanha a animação de altura) e quando `data-active` muda. */
function usePilulaAtiva(
  navRef: React.RefObject<HTMLDivElement | null>,
  pilulaRef: React.RefObject<HTMLSpanElement | null>,
  chave: string
) {
  useLayoutEffect(() => {
    const nav = navRef.current
    const pilula = pilulaRef.current
    if (!nav || !pilula) return
    const medir = () => posicionarPilula(pilula, nav)
    medir()
    // Liga a transição só depois do 1º posicionamento (sem deslizar do topo ao montar).
    const raf = requestAnimationFrame(() => marcarPronta(pilula))
    const ro = new ResizeObserver(medir)
    ro.observe(nav)
    const mo = new MutationObserver(medir)
    mo.observe(nav, {
      attributes: true,
      subtree: true,
      childList: true,
      attributeFilter: ["data-active", "data-state"],
    })
    return () => {
      cancelAnimationFrame(raf)
      ro.disconnect()
      mo.disconnect()
    }
  }, [navRef, pilulaRef, chave])
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
  const { isMobile, setOpenMobile, state } = useSidebar()
  const navRef = useRef<HTMLDivElement>(null)
  const pilulaRef = useRef<HTMLSpanElement>(null)
  usePilulaAtiva(navRef, pilulaRef, `${pathname}|${state}`)
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
          <SidebarGroupContent ref={navRef} className="relative">
            {/* Pílula do item ativo: uma só, que DESLIZA até o item clicado (em vez de o fundo
                piscar de um item para o outro). Os itens ativos ficam com fundo transparente. */}
            <span
              ref={pilulaRef}
              aria-hidden
              className="pointer-events-none absolute top-0 left-0 rounded-full bg-sidebar-accent opacity-0 data-pronto:transition-[transform,width,height,opacity] data-pronto:duration-300 data-pronto:ease-(--ease-out) motion-reduce:transition-none"
            />
            <SidebarMenu className="relative [&_[data-active=true]]:bg-transparent">
              {!somenteDivisao && (
                <>
                  <NavItemButton item={inicioItem} pathname={pathname} />
                  <NavItemButton item={dashboardItem} pathname={pathname} />
                </>
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
        {/* Recolher/expandir fica no rodapé, junto do usuário: é controle do shell, não destino —
            não disputa o topo com a navegação. No mobile (gaveta) não há o que recolher. */}
        {isMobile ? null : (
          <SidebarMenu>
            <BotaoRecolher />
          </SidebarMenu>
        )}
        <NavUser />
      </SidebarFooter>

      <SidebarRail />
    </Sidebar>
  )
}
