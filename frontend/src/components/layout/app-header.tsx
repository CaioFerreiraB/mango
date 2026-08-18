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
import { Separator } from "@/components/ui/separator"
import { SidebarTrigger } from "@/components/ui/sidebar"

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
    <header className="flex h-14 shrink-0 items-center gap-2 px-4">
      {/* No mobile a navegação é a bottom bar: o hambúrguer (e o pipe) somem, sobra o breadcrumb. */}
      <SidebarTrigger className="-ml-1 hidden md:flex" />
      {/* self-center! sobrepõe o data-vertical:self-stretch do Separator, que com altura fixa prenderia o pipe no topo */}
      <Separator
        orientation="vertical"
        className="mr-2 hidden h-4 self-center! md:block"
      />

      <Breadcrumb>
        <BreadcrumbList>
          {crumbs.map((crumb, index) => {
            const isLast = index === crumbs.length - 1
            return (
              <Fragment key={crumb.pathname}>
                <BreadcrumbItem>
                  {isLast ? (
                    <BreadcrumbPage>{crumb.title}</BreadcrumbPage>
                  ) : (
                    <BreadcrumbLink asChild>
                      <Link to={crumb.pathname}>{crumb.title}</Link>
                    </BreadcrumbLink>
                  )}
                </BreadcrumbItem>
                {isLast ? null : <BreadcrumbSeparator />}
              </Fragment>
            )
          })}
        </BreadcrumbList>
      </Breadcrumb>
    </header>
  )
}
