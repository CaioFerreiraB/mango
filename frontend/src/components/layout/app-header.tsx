import { Fragment, useEffect, useState } from "react"
import { Link, useMatches } from "react-router"

import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"
import { Menu } from "lucide-react"

import { ChatToggle } from "@/components/chat/chat-panel"
import { BuscaGlobal } from "@/components/layout/busca-global"
import { BOTAO_TOPO_MOBILE } from "@/components/layout/topo"
import { Button } from "@/components/ui/button"
import { useSidebar } from "@/components/ui/sidebar"
import { cn } from "@/lib/utils"

type RouteHandle = { title?: string }

function useBreadcrumbs() {
  const matches = useMatches()
  return matches
    .map((match) => ({
      pathname: match.pathname,
      title: (match.handle as RouteHandle | undefined)?.title,
    }))
    .filter((crumb): crumb is { pathname: string; title: string } =>
      Boolean(crumb.title)
    )
}

/** A página rolou do topo? (atualiza só quando o estado muda; listener passivo). */
function useRolou(): boolean {
  const [rolou, setRolou] = useState(false)
  useEffect(() => {
    const ver = () => setRolou(window.scrollY > 12)
    ver()
    window.addEventListener("scroll", ver, { passive: true })
    return () => window.removeEventListener("scroll", ver)
  }, [])
  return rolou
}

export function AppHeader() {
  const crumbs = useBreadcrumbs()
  const { openMobile, setOpenMobile } = useSidebar()
  const rolou = useRolou()

  return (
    // Mobile (proposta C, "título grande que encolhe"): no topo a barra é transparente, só com os
    // botões redondos — o título grande é o h1 da própria página; ao rolar, ganha vidro (branco
    // fundo branco sólido, cantos de baixo levemente arredondados (encostada nas bordas da tela) e
    // uma sombra leve — sem linha; o nome da página aparece pequeno no centro. Desktop: faixa como antes.
    <header
      data-rolou={rolou}
      className="group/topo sticky top-0 z-30 flex h-[calc(3.75rem+env(safe-area-inset-top))] shrink-0 items-center gap-2 px-4 pt-[env(safe-area-inset-top)] transition-[background-color,box-shadow,border-radius] duration-300 ease-(--ease-out) data-[rolou=true]:rounded-b-[1.25rem] data-[rolou=true]:bg-background data-[rolou=true]:shadow-[0_4px_14px_-8px_rgb(16_24_40/0.16)] motion-reduce:transition-none md:static md:h-16 md:px-8 md:pt-0 md:data-[rolou=true]:rounded-none md:data-[rolou=true]:bg-transparent md:data-[rolou=true]:shadow-none"
    >
      {/* Mobile: o menu lateral (navegação completa) abre por aqui, por cima da página. */}
      <Button
        variant="ghost"
        size="icon-sm"
        className={cn("md:hidden", BOTAO_TOPO_MOBILE)}
        aria-label="Abrir menu"
        aria-expanded={openMobile}
        onClick={() => setOpenMobile(true)}
      >
        <Menu className="size-5" aria-hidden />
      </Button>
      {/* Desktop: com um nível só o breadcrumb repetiria o h1 da página — some; volta nos detalhes. */}
      {/* Mobile: o nome da página (pequeno, no centro) só aparece depois de rolar. */}
      <Breadcrumb
        className={cn(
          "min-w-0 motion-reduce:transition-none max-md:pointer-events-none max-md:absolute max-md:inset-x-16 max-md:bottom-0 max-md:flex max-md:h-[3.75rem] max-md:translate-y-1 max-md:items-center max-md:justify-center max-md:opacity-0 max-md:transition-[opacity,transform] max-md:duration-300 max-md:ease-(--ease-out) max-md:group-data-[rolou=true]/topo:pointer-events-auto max-md:group-data-[rolou=true]/topo:translate-y-0 max-md:group-data-[rolou=true]/topo:opacity-100",
          crumbs.length === 1 && "md:hidden"
        )}
      >
        <BreadcrumbList className="flex-nowrap">
          {crumbs.map((crumb, index) => {
            const isLast = index === crumbs.length - 1
            return (
              <Fragment key={crumb.pathname}>
                {/* Mobile: só a página atual (o caminho não cabe ao lado do botão). */}
                <BreadcrumbItem
                  className={isLast ? "min-w-0" : "hidden md:inline-flex"}
                >
                  {isLast ? (
                    <BreadcrumbPage className="truncate font-extrabold max-md:text-base md:font-normal">
                      {crumb.title}
                    </BreadcrumbPage>
                  ) : (
                    <BreadcrumbLink asChild>
                      <Link to={crumb.pathname}>{crumb.title}</Link>
                    </BreadcrumbLink>
                  )}
                </BreadcrumbItem>
                {isLast ? null : (
                  <BreadcrumbSeparator className="hidden md:block" />
                )}
              </Fragment>
            )
          })}
        </BreadcrumbList>
      </Breadcrumb>
      <div className="ml-auto flex flex-1 items-center justify-end gap-2 md:ml-4 md:gap-1">
        <BuscaGlobal />
        <ChatToggle />
      </div>
    </header>
  )
}
