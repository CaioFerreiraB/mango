import { Fragment } from "react"
import { Link, useMatches } from "react-router"

import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"
import { ChatToggle } from "@/components/chat/chat-panel"
import { BuscaGlobal } from "@/components/layout/busca-global"

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

export function AppHeader() {
  const crumbs = useBreadcrumbs()

  return (
    // Mobile: topbar fixa (sticky + safe-area do notch) com o título da página e o assistente.
    // Desktop: faixa do inset como antes, com o assistente no canto direito.
    <header className="sticky top-0 z-30 flex h-[calc(3.5rem+env(safe-area-inset-top))] shrink-0 items-center gap-2 border-b bg-background/90 px-4 pt-[env(safe-area-inset-top)] backdrop-blur-md md:static md:h-14 md:border-b-0 md:bg-transparent md:pt-0 md:backdrop-blur-none">
      <Breadcrumb className="min-w-0">
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
                    <BreadcrumbPage className="truncate font-medium md:font-normal">
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
      <div className="ml-auto flex flex-1 items-center justify-end gap-1 md:ml-4">
        <BuscaGlobal />
        <ChatToggle />
      </div>
    </header>
  )
}
